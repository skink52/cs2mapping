"""What every IRONFRAME arena shares: the mesh/prop/lamp helpers an arena module builds its world with (Ctx), and
finish_arena(), which adds everything the script needs (INTERFACES.md section 7) around the arena the module built:
sky shell (moondome + toolsskybox), sun / sky / fog / post entities, probe volumes, lightmap-res shells, vis hints,
drop zones, Conquest points, the sealed pawn booth with 64 spawns, the cache room (models.json), the prop pool template,
mailboxes, point_soundevents (sounds.json or the adapter's fallback list), particle pools, script / HUD / map params,
nav seed, minimap bounds, the nav grid + arena.json, previews, loading slides and the radar.

An arena module exposes  build(ctx) -> dict  with:
  bounds      ((x0, y0, z0), (x1, y1, z1))            play bounds (INTERFACES section 2); z0 is the death height
  ground(X,Y) -> Z                                     ground the nav grid uses: terrain + tops of things a mech stands on
  solid(X,Y)  -> bool                                  inside an obstacle (never walkable); None = nothing
  struct      [(x0, y0, x1, y1), ...]                  footprints of buildings / bridges / platforms (nav.struct within 2 cells)
  walk_ok(X,Y)-> bool  (optional)                      extra walkability mask (platform edges, water)
  points      [(id, (x, y, z), radius), ...]           A, B, C
  drops       {'t': [(x,y,z,yaw)], 'ct': [...], 'ffa': [...]}
  landmarks   [(name, (x, y, z)), ...]
  env         dict(sun_angles, sun_color, sun_brightness, sky_color, sky_intensity, sky_tint, sky_brightness, fog(dict of env_cubemap_fog keys),
                   vfog(dict), exposure (min, max), ambient (lumens, colour) for the booth/cache lamps)
  shell       (x0, y0, z0, x1, y1, z1) sky shell box;  play (x0,y0,z0,x1,y1,z1) the volume probes / hints cover
  hints       [(box, kind), ...] extra visibility hints (Lower over the structure band, Low in sealed rooms)
  lmres       'terrain' (ground sampled on a 256 grid) or a list of boxes
  radar_zones(X,Y) -> (nx, ny, 3) float colour 0..1 for the relief picture (optional)
"""
import os, sys, math, json
import numpy as np
from PIL import Image, ImageDraw
import dmx, vmaplib, vmesh, voxel, fx_models
import vmapgen as G
from vmaplib import ent
from noise import fbm, smoothstep

PREFIX = 'ifr'
NAV_CELL = 256
MECH_H = 300.0          # the tallest frame with clearance
PASSAGE = 600.0         # minimum gap a mech may be asked to pass through

# stock materials (checked against the CS2 VPK index, 9 Nov 2026)
M = dict(
    sand_blend='materials/de_dust/hr_dust/hr_dust_blend_sand02_sand03.vmat',               # A sand02, B sand03
    rock_blend='materials/de_dust/hr_dust/hr_dust_blend_groundstone01-groundsmooth01.vmat',  # A stone, B smooth ground
    sand='materials/de_dust/hr_dust/hr_dust_sand_02.vmat', stone='materials/de_dust/hr_dust/hr_dust_ground_stone_01.vmat',
    concrete='materials/concrete/hr_c/hr_concrete_wall_006.vmat', concrete2='materials/de_overpass/concrete/concrete_12.vmat',
    concrete_floor='materials/de_overpass/concrete/concrete_floor_4.vmat', concrete_dark='materials/concrete/hr_c/hr_concrete_floor_001_dark.vmat',
    metal_floor='materials/de_nuke/nuke_metalfloor_01.vmat', grate='materials/de_nuke/nuke_metalgrate_01.vmat',
    rust='materials/de_overpass/metal/rusty_metal_1.vmat', corrugated='materials/metal/hr_metal/hr_metal_corrugated_001_grey.vmat',
    corrugated_orange='materials/metal/hr_metal/hr_metal_corrugated_001_orange.vmat', panel='materials/de_train/hr_train_s2/metal/hrts2_metal_panelling_01.vmat',
    steel_plate='materials/de_overpass/metal/steel_ground_plate_1.vmat', metal_trim='materials/de_nuke/hr_nuke/hr_metal_trim_001.vmat',
    asphalt='materials/de_overpass/asphalt/asphalt_road_worn_01.vmat', asphalt2='materials/de_nuke/hr_nuke/hr_asphalt_001.vmat',
    windows_lit='materials/de_overpass/buildings/building_windows_03_lit.vmat', windows='materials/de_overpass/buildings/building_windows_01.vmat',
    window_glass_lit='materials/glass/window_opaque_1b_lit.vmat', roof_metal='materials/de_overpass/buildings/roof_metal_painted_1.vmat',
    water='materials/liquids/nuke_water.vmat', nodraw='materials/tools/toolsnodraw.vmat', clip='materials/tools/toolsplayerclip.vmat',
    trigger='materials/tools/toolstrigger.vmat')
for _m in M.values(): vmesh.TEX_SIZE.setdefault(_m, (1024, 1024))
vmesh.TEX_SIZE[M['nodraw']] = (64, 64); vmesh.TEX_SIZE[M['clip']] = (64, 64); vmesh.TEX_SIZE[M['trigger']] = (64, 64)

# stock props (paths checked in the VPK index)
P = dict(
    container='models/generic/shipping_container_01/shipping_container_01_120x288x136_01.vmdl',
    container_s='models/generic/shipping_container_01/shipping_container_01_120x160x136_01.vmdl',
    silo='models/props/de_nuke/hr_nuke/medium_silo/medium_silo.vmdl', cooling='models/props/de_nuke/coolingtank.vmdl',
    silo_a='models/props/de_train/hr_t/silo_a/silo_a.vmdl', radio_tower='models/props/de_overpass/radio_tower.vmdl',
    cell_tower='models/props/de_dust/hr_dust/dust_cell_tower/dust_cell_tower.vmdl',
    pipe1024='models/props/de_nuke/hr_nuke/metal_pipe_001/metal_pipe_001_straight_1024.vmdl',
    pipe512='models/props/de_nuke/hr_nuke/metal_pipe_001/metal_pipe_001_straight_512.vmdl',
    garbage='models/props/de_dust/hr_dust/dust_garbage_container/dust_garbage_container.vmdl',
    tanker='models/props/de_train/hr_train_s2/train_railcars/train_railcar_tanker_car_01.vmdl',
    crane='models/props/de_overpass/crane.vmdl', antenna='models/props/de_dust/hr_dust/dust_anteanna/dust_antenna_thick_01.vmdl',
    bg_silo='models/props/de_train/hr_train_s2/train_silo_bg/train_silo_bg_silo_01.vmdl')

# the adapter's sound list when sounds.json is missing (coordinator, 9 Nov 2026); event names ifr.<key>
WEAPON_KEYS = ['rifle', 'gatling', 'shotgun', 'laser', 'bazooka', 'grenade', 'blade', 'plasma', 'rail', 'handmsl', 'shield', 'smg', 'vm6', 'dualmsl',
               'lasercannon', 'grenadecannon', 'autocannon', 'flak', 'pulseshield', 'repair', 'decoy', 'vm12']
SOUND_SINGLES = ('laser_charge rail_charge lasercannon_charge hit_metal hit_ground boom_small boom_large mech_death stagger_clang qb boost_on_light '
                 'boost_on_medium boost_on_heavy land_light land_heavy drop_entry capture_tick capture_done wave_start boss_roar bounty ui_lock1 ui_lock2 '
                 'ui_lock3 ui_locked_warn ui_launch_warn ui_msl_close ui_hit ui_kill ui_stagger ui_low_ap ui_en_empty ui_en_ok ui_ready ui_spawn ui_capture '
                 'ui_round_start ui_podium ui_garage_move ui_garage_ok ui_garage_deny music_garage music_battle').split()
SOUND_RINGS = {'boost_loop': 64, 'msl_loop': 24, 'gatling_loop': 16}
# particle pools (INTERFACES section 7): kind -> (count, digits, stock effect)
PFX = [('boost', 128, 3, 'particles/burning_fx/env_fire_small_b.vpcf'), ('muzzle', 64, 2, 'particles/weapons/cs_weapon_fx/weapon_muzzle_flash_assaultrifle.vpcf'),
       ('boom', 24, 2, 'particles/explosions_fx/explosion_c4_500.vpcf'), ('spark', 16, 2, 'particles/impact_fx/impact_metal.vpcf'),
       ('gboom', 8, 2, 'particles/explosions_fx/explosion_hegrenade.vpcf'), ('trail', 128, 3, 'particles/burning_fx/gas_cannister_trail_smoke.vpcf')]

BOOTH = (0.0, 0.0, -12000.0)          # pawn booth origin (floor); 1024 x 1024 x 512
CACHE = (3072.0, 0.0, -12000.0)       # cache room origin (floor); 3072 x 1536 x 512
BOOTH_HALF, CACHE_W, CACHE_D, ROOM_H = 512.0, 3072.0, 1536.0, 512.0


def rotz(yaw_deg, pitch_deg=0.0, roll_deg=0.0):
    """Hammer-style rotation: yaw about z, then pitch about the rotated y (positive pitch = nose down), then roll about x"""
    cy, sy = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    cp, sp = math.cos(math.radians(pitch_deg)), math.sin(math.radians(pitch_deg))
    cr, sr = math.cos(math.radians(roll_deg)), math.sin(math.radians(roll_deg))
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1.0]])
    Ry = np.array([[cp, 0, sp], [0, 1.0, 0], [-sp, 0, cp]])
    Rx = np.array([[1.0, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def rot_bbox(cx, cy, hx, hy, yaw_deg, z0, z1, walk_top=False):
    """axis-aligned box round a yawed footprint (for the nav grid's solid / ground lists)"""
    c, s = abs(math.cos(math.radians(yaw_deg))), abs(math.sin(math.radians(yaw_deg)))
    ex, ey = hx * c + hy * s, hx * s + hy * c
    return (cx - ex, cy - ey, z0, cx + ex, cy + ey, z1, walk_top)


class Ctx:
    """mesh / prop / light helpers bound to the open map; arena modules only use these (plus vmapgen for terrain)"""

    def __init__(self, d, out, arena, group, rng_seed=1):
        self.d, self.out, self.arena, self.group = d, out, arena, group
        self.rng = np.random.RandomState(rng_seed)
        self.n_mesh = self.n_prop = self.n_light = 0
        self.shadowed = []            # (x, y, z, range) of shadow-casting lights: at most 4 may overlap

    # ---- meshes
    def mesh(self, m, bake=True, shadows=True, visexclude=False, physics='default'):
        self.n_mesh += 1
        return vmesh.mesh_node(m, self.group, bake=bake, shadows=shadows, visexclude=visexclude, physics=physics)

    def box(self, b, mats, **kw):
        """closed axis-aligned box (x0, y0, z0, x1, y1, z1); mats: one material or dict(top, bottom, side)"""
        return self.mesh(vmesh.box_mesh(*b, mats), **kw)

    def obox(self, center, half, yaw=0.0, pitch=0.0, roll=0.0, mats=None, **kw):
        """oriented box: half extents in its own frame (x forward, y left, z up), rotated by yaw/pitch/roll"""
        fm = mats if isinstance(mats, str) else [mats.get('bottom', mats['side']), mats.get('top', mats['side'])] + [mats['side']] * 4
        return self.mesh(vmesh.oriented_box_mesh(center, half, rotz(yaw, pitch, roll), fm), **kw)

    def cylinder(self, p0, p1, r, mats, n=16, **kw):
        """closed n-gon prism from p0 to p1 (any direction); mats: one material or dict(side, cap)"""
        p0 = np.asarray(p0, float); p1 = np.asarray(p1, float)
        axis = p1 - p0; L = np.linalg.norm(axis); a = axis / L
        up = np.array([0, 0, 1.0]) if abs(a[2]) < 0.9 else np.array([1.0, 0, 0])
        u = np.cross(a, up); u /= np.linalg.norm(u); v = np.cross(a, u)
        th = np.arange(n) * 2 * np.pi / n
        ring0 = [p0 + r * (math.cos(t) * u + math.sin(t) * v) for t in th]
        ring1 = [p1 + r * (math.cos(t) * u + math.sin(t) * v) for t in th]
        verts = ring0 + ring1
        # with a = u x v the ring (u cos, v sin) runs CCW seen from +a: top cap CCW from outside, bottom cap reversed
        faces = [list(range(n))[::-1], [n + i for i in range(n)]]
        for i in range(n):
            j = (i + 1) % n
            faces.append([i, j, n + j, n + i])
        side = mats if isinstance(mats, str) else mats['side']; cap = mats if isinstance(mats, str) else mats.get('cap', side)
        fm = [cap, cap] + [side] * n
        return self.mesh(vmesh.polymesh_open(verts, faces, fm, scale=0.25), **kw)

    def sheet(self, verts, faces, mats, **kw):
        return self.mesh(vmesh.polymesh_open(verts, faces, mats if isinstance(mats, list) else [mats] * len(faces), scale=0.25), **kw)

    def water(self, b):
        """a water sheet: the top face is the water material, the rest nodraw; depth <= 5 u (guide: water sheets never overlap)"""
        x0, y0, z0, x1, y1, z1 = b
        z0 = max(z0, z1 - 5)
        m = vmesh.box_mesh(x0, y0, z0, x1, y1, z1, dict(top=M['water'], side=M['nodraw'], bottom=M['nodraw']))
        return self.mesh(m, bake=False, shadows=False, visexclude=True, physics='none')

    # ---- props and lights
    def prop(self, model, origin, yaw=0.0, scale=1.0, pitch=0.0, roll=0.0, solid='6', bake=None, shadows='0', **kw):
        s = (scale, scale, scale) if not isinstance(scale, (tuple, list)) else tuple(scale)
        if bake is None: bake = '1' if max(s) >= 1.0 else '0'
        keys = dict(model=model, solid=solid, disableshadows=shadows, fademindist='-1', fademaxdist='0', rendertocubemaps='1',
                    bakelighting=bake, visoccluder='0', skin='default', rendercolor='255 255 255', renderamt='255', lodlevel='-1', baketoworld='0')
        keys.update(kw)
        e = ent('prop_static', origin, (pitch, yaw, roll), group=self.group, **keys)
        if tuple(s) != (1.0, 1.0, 1.0): e.attr('scales')[2] = tuple(float(x) for x in s)
        self.n_prop += 1
        return e

    def lamp(self, origin, lumens, rng, color='255 220 180', shadows=False, baked_only=False):
        """light_omni2: Stationary (directlight 3) unless baked_only; shadows only where fewer than 4 shadowed lights already overlap"""
        if shadows:
            x, y, z = origin
            if sum(1 for (lx, ly, lz, lr) in self.shadowed if math.dist((x, y, z), (lx, ly, lz)) < lr + rng) >= 3: shadows = False
            else: self.shadowed.append((x, y, z, rng))
        self.n_light += 1
        return ent('light_omni2', origin, (90, 0, 0), group=self.group, brightness_units='1', brightness_lumens=str(int(lumens)), brightness='1',
                   color=color, range='%.0f' % rng, directlight='1' if baked_only else '3', castshadows='1' if shadows else '0', colormode='0',
                   enabled='1', bouncescale='1.0', shape='0')

    def target(self, name, origin, yaw=0.0):
        return ent('info_target', origin, (0, yaw, 0), group=self.group, targetname=name)

    def clone(self, cls, origin, angles=(0, 0, 0), **keys):
        return G.clone(self.d, cls, origin, angles, group=self.group, **keys)


# ---------------------------------------------------------------- shared rooms far below the arena
def room(ctx, b, mats, lumens, color, n_lamps=4):
    x0, y0, z0, x1, y1, z1 = b
    ctx.mesh(vmesh.box_mesh(x0, y0, z0, x1, y1, z1, mats, inward=True))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; hx, hy = (x1 - x0) / 2, (y1 - y0) / 2
    if n_lamps >= 4:
        for sx in (-1, 1):
            for sy in (-1, 1): ctx.lamp((cx + sx * hx * 0.5, cy + sy * hy * 0.5, z1 - 40), lumens, max(hx, hy) * 1.2, color)
    ctx.lamp((cx, cy, z1 - 40), lumens * 1.2, max(hx, hy) * 1.5, color, shadows=True)
    G.probe_volume(b, voxel=48, group=ctx.group, indoor_outdoor_level='2')
    G.lmres_box(b, group=ctx.group)
    G.hint((x0 - 16, y0 - 16, z0 - 16, x1 + 16, y1 + 16, z1 + 16), 'Low', group=ctx.group)


def booth(ctx, env):
    """the sealed pawn booth: 32 + 32 spawns, lit, nav seed, map params, script, HUD, team intro clones, ifr_booth"""
    bx, by, bz = BOOTH; h = BOOTH_HALF
    b = (bx - h, by - h, bz, bx + h, by + h, bz + ROOM_H)
    room(ctx, b, dict(bottom=M['metal_floor'], top=M['concrete_dark'], side=M['panel']), env.get('ambient', (3000, '255 220 180'))[0], env.get('ambient', (3000, '255 220 180'))[1])
    for i in range(32):
        x = bx - 420 + (i % 8) * 120; y = by - 440 + (i // 8) * 110
        ent('info_player_terrorist', (x, y, bz + 8), (0, 90, 0), group=ctx.group, enabled='1', priority='0')
        ent('info_player_counterterrorist', (x, by + 440 - (i // 8) * 110, bz + 8), (0, 270, 0), group=ctx.group, enabled='1', priority='0')
    ctx.target('%s_booth' % PREFIX, (bx, by, bz + 8))
    G.nav_seed((bx - 400, by - 64, bz + 1, bx + 400, by + 64, bz + 40), group=ctx.group)
    G.map_params((bx - 64, by, bz + 64), name='%s_map_params' % PREFIX, group=ctx.group)
    import names as N
    ent('point_script', (bx, by, bz + 64), group=ctx.group, targetname='%s_script' % PREFIX, cs_script=N.SCRIPT_PATH)
    ent('custom_hud_layout', (bx + 32, by, bz + 64), group=ctx.group, targetname='%s_hud' % PREFIX, layout=N.HUD_PATH, observable='1')
    for cls, pos, yaw in (('counterterrorist_team_intro', (bx + 300, by + 300, bz + 64), 90), ('terrorist_team_intro', (bx - 300, by + 300, bz + 64), 90),
                          ('team_select', (bx, by - 300, bz + 64), 90), ('end_of_match', (bx, by, bz + 64), 90)):
        ctx.clone(cls, pos, (0, yaw, 0))
    ctx.clone('env_soundscape', (bx, by, bz + 200), radius='-1', soundscape='Nothing', enablesoundevent='0', soundevent='')
    return (bx, by, bz)


def _flatten_strings(o, out):
    if isinstance(o, str): out.append(o)
    elif isinstance(o, dict):
        for v in o.values(): _flatten_strings(v, out)
    elif isinstance(o, list):
        for v in o: _flatten_strings(v, out)


def sound_names(gen_dir):
    """[(targetname suffix, event, stop_on_new)] from _gen/sounds.json, else the adapter's fallback list.
    sounds.json forms understood: {"events": {key: {"event": "ifr.x", "per_slot": 64 | "ring": N}}} or {key: "ifr.x"} / {key: {...}},
    or a plain list of event names. Keys with per_slot / ring N get N entities key_NN."""
    p = os.path.join(gen_dir, 'sounds.json')
    items = []
    if os.path.exists(p):
        j = json.load(open(p))
        ev = j.get('events', j) if isinstance(j, dict) else j
        if isinstance(ev, list):
            for e in ev: items.append((e.split('.')[-1], e, 1, 1 if e.split('.')[-1].startswith('music') else 0))
        else:
            groups = [ev] + [j[g] for g in ('music', 'pilot_tones') if isinstance(j, dict) and isinstance(j.get(g), dict)]
            seen = set()
            for grp in groups:
                for k, v in grp.items():
                    if k in seen: continue
                    if isinstance(v, str): e, n, stop = v, 1, 1 if k.startswith('music') else 0
                    elif isinstance(v, dict):
                        e = v.get('event') or v.get('name') or ('ifr.' + k); n = int(v.get('per_slot') or v.get('ring') or 1)
                        stop = 1 if (k.startswith('music') or v.get('stop_on_new') is True) else 0
                    else: continue
                    if not isinstance(e, str) or '.' not in e: continue
                    seen.add(k); items.append((k, e, n, stop))
        if not items:
            s = []; _flatten_strings(j, s)
            items = [(e.split('.')[-1], e, 1, 0) for e in dict.fromkeys(s) if e.startswith('ifr.')]
    if not items:
        for k in WEAPON_KEYS + SOUND_SINGLES: items.append((k, 'ifr.' + k, 1, 1 if k.startswith('music') else 0))
        for k, n in SOUND_RINGS.items(): items.append((k, 'ifr.' + k, n, 0))
    out = []
    for k, e, n, stop in items:
        if n <= 1: out.append((k, e, stop))
        else: out += [('%s_%02d' % (k, i), e, stop) for i in range(n)]
    return out


def particle_names(gen_dir):
    p = os.path.join(gen_dir, 'fx_particles.json')
    custom = json.load(open(p)) if os.path.exists(p) else {}
    pools = custom.get('pools', custom) if isinstance(custom, dict) else {}
    out = []
    for kind, n, digits, stock in PFX:
        eff = pools.get(kind, stock)
        if isinstance(eff, dict): eff = eff.get('effect') or eff.get('path') or stock
        out += [('%s_pfx_%s_%0*d' % (PREFIX, kind, digits, i), eff) for i in range(n)]     # counts are INTERFACES section 7's, names fixed
    ap = os.path.join(gen_dir, 'auras.json')                                                # frame aura flare pools (tools/auras.py)
    for kind, pool in sorted(((json.load(open(ap)) if os.path.exists(ap) else {}).get('pools') or {}).items()):
        out += [('%s_pfx_%s_%02d' % (PREFIX, kind, i), pool['effect']) for i in range(int(pool.get('count', 4)))]
    return out


def cache(ctx, env, gen_dir, null_model):
    """cache room: a prop_dynamic per script model, the prop pool template, 64 mailboxes, the sound events and the particle pools"""
    cx, cy, cz = CACHE
    b = (cx - CACHE_W / 2, cy - CACHE_D / 2, cz, cx + CACHE_W / 2, cy + CACHE_D / 2, cz + ROOM_H)
    room(ctx, b, dict(bottom=M['concrete_floor'], top=M['concrete_dark'], side=M['concrete']), 2500, '255 230 200')
    models = [null_model]
    mp = os.path.join(gen_dir, 'models.json')
    if os.path.exists(mp):
        j = json.load(open(mp))
        for fr in (j.get('frames') or {}).values():
            for k in ('legs', 'upper'):
                if fr.get(k): models.append(fr[k])
        for v in (j.get('weapons') or {}).values():
            if isinstance(v, str): models.append(v)
        for v in (j.get('fx') or {}).values():
            if isinstance(v, str): models.append(v)
    ap = os.path.join(gen_dir, 'auras.json')                                                # frame aura models (tools/auras.py)
    if os.path.exists(ap):
        for fr in (json.load(open(ap)).get('frames') or {}).values():
            for part in (fr.get('parts') or {}).values(): models += list((part.get('states') or {}).values())
    models = list(dict.fromkeys(models))
    n_cache = G.cache_room(ctx.d, models, (cx, cy - 256, cz), size=(CACHE_W - 128, CACHE_D - 640), step=(96, 96), prefix='%s_cache_' % PREFIX, group=ctx.group)
    G.template_pool('%s_tpl_prop' % PREFIX, (cx - CACHE_W / 2 + 96, cy + CACHE_D / 2 - 96, cz + 8), null_model, group=ctx.group)
    for i in range(64):
        ctx.target('%s_mail_%02d' % (PREFIX, i), (cx - CACHE_W / 2 + 128 + (i % 16) * 64, cy + CACHE_D / 2 - 200 - (i // 16) * 64, cz + 300))
        for q in range(4):     # origin-encoding fallback (MailboxMode "origin"): the plugin Teleports these when AddOutput targetname is refused
            ctx.target('%s_mail_%02d_%d' % (PREFIX, i, q), (cx - CACHE_W / 2 + 128 + (i % 16) * 64 + q * 12, cy + CACHE_D / 2 - 200 - (i // 16) * 64, cz + 360))
    snd = sound_names(gen_dir)
    names = [k for k, e, s in snd]
    ev_of = {k: e for k, e, s in snd}; stop_of = {k: s for k, e, s in snd}
    # vmapgen.sound_events names entities prefix + event; we need prefix + key, so place them ourselves on a grid
    have = {G.props_of(c).get('targetname') for c in G.entities(ctx.d) if G.props_of(c).get('classname') == 'point_soundevent' and c.get('customVisGroup', '') != ctx.group}
    k = 0
    for name in names:
        tn = '%s_snd_%s' % (PREFIX, name)
        if tn in have: continue
        ent('point_soundevent', (cx - CACHE_W / 2 + 96 + (k % 30) * 96, cy - CACHE_D / 2 + 96 + (k // 30) * 64, cz + 380), group=ctx.group, targetname=tn,
            soundName=ev_of[name], startOnSpawn='0', toLocalPlayer='0', stopOnNew=str(stop_of[name]), saveAndRestore='0')
        k += 1
    pf = particle_names(gen_dir)
    for i, (tn, eff) in enumerate(pf):
        ent('info_particle_system', (cx - CACHE_W / 2 + 96 + (i % 30) * 96, cy - CACHE_D / 2 + 96 + (i // 30) * 48, cz + 440), group=ctx.group, targetname=tn,
            effect_name=eff, start_active='0')
    print('cache room: %d models (%d new props), %d sound events, %d particle pool entities, 64 mailboxes' % (len(models), n_cache, k, len(pf)))
    return (cx, cy, cz), dict(models=len(models), sounds=k, particles=len(pf))


# ---------------------------------------------------------------- environment
def environment(ctx, A, dome_mat, sky_mat):
    env = A['env']; sx0, sy0, sz0, sx1, sy1, sz1 = A['shell']
    G.moondome(A['shell'], dome_mat, group=ctx.group, toolsskybox=True)
    c = ((sx0 + sx1) / 2, (sy0 + sy1) / 2)
    top = sz1 - 200
    ctx.clone('light_environment', (c[0], c[1], top), env['sun_angles'], targetname='%s_sun' % PREFIX, color=env['sun_color'], brightness=str(env['sun_brightness']),
              castshadows='1', directlight='3', skycolor=env['sky_color'], skyintensity=str(env['sky_intensity']), skytexture='%s_sky' % PREFIX, fog='1',
              fogstrength=str(env.get('sun_fog', 0.6)), angulardiameter=str(env.get('sun_diameter', 0.6)))
    ctx.clone('env_sky', (c[0] + 64, c[1], top), targetname='%s_sky' % PREFIX, skyname=sky_mat, tint_color=env.get('sky_tint', '255 255 255'),
              brightnessscale=str(env.get('sky_brightness', 1.0)))
    fog = dict(cubemapfogstartdistance='400', cubemapfogenddistance='9000', cubemapfogfalloffexponent='1.25', cubemapheightfog='1', cubemapfogheightstart='300.0',
               cubemapfogheightend='2600.0', cubemapfogheightexponent='1.0', cubemapfogmaxopacity='0.85', cubemapfogskyentity='%s_sky' % PREFIX, cubemapfogsource='1')
    fog.update({k: str(v) for k, v in env.get('fog', {}).items()})
    ctx.clone('env_cubemap_fog', (c[0] + 128, c[1], top), **fog)
    vf = dict(IsMaster='1', FogStrength='0.6', TintColor='205 210 215', DrawDistance='1600', FadeInStart='40', FadeInEnd='300', FadeSpeed='2', IndirectEnabled='1',
              IndirectStrength='1.0', IndirectVoxelDim='256', NoiseSpeed='0.15', NoiseStrength='0.55', NoiseScale='.004 .004 .01', volume_depth_override='0',
              volume_first_slice_thickness='0')
    vf.update({k: str(v) for k, v in env.get('vfog', {}).items()})
    ent('env_volumetric_fog_controller', (c[0] + 192, c[1], top), group=ctx.group, targetname='%s_vfog' % PREFIX, **vf)
    e0, e1 = env.get('exposure', (0.6, 1.8))
    ctx.clone('post_processing_volume', (c[0] + 256, c[1], top), master='1', minexposure=str(e0), maxexposure=str(e1), enableexposure='1', fadetime='1.0',
              spawnflags='4097', postprocessing=env.get('post', 'postprocess/basic_linear_post.vpost'))   # an arena's own look: tools/arenas/post.py
    # minimap corners
    (x0, y0, z0), (x1, y1, z1) = A['bounds']
    ent('cs_minimap_boundary', (x0, y0, z0), group=ctx.group); ent('cs_minimap_boundary', (x1, y1, z1), group=ctx.group)


def probes_and_lmres(ctx, A):
    """probe volumes: 3 x 3 at voxel 64 over the play volume up to z 1200 (priority 1), 2 x 2 at 108 over the air (priority 0);
    toolslightmapres over the play surface"""
    px0, py0, pz0, px1, py1, pz1 = A['play']
    (bx0, by0, bz0), (bx1, by1, bz1) = A['bounds']
    gz1 = A.get('ground_probe_top', 1200.0)
    xs = np.linspace(px0, px1, 4); ys = np.linspace(py0, py1, 4)
    n = 0
    for i in range(3):
        for j in range(3):
            G.probe_volume((xs[i], ys[j], pz0, xs[i + 1], ys[j + 1], gz1), voxel=64, group=ctx.group, name='%s_probe_g%d' % (PREFIX, n), indoor_outdoor_level='1'); n += 1
    xs = np.linspace(px0, px1, 3); ys = np.linspace(py0, py1, 3)
    for i in range(2):
        for j in range(2):
            G.probe_volume((xs[i], ys[j], gz1, xs[i + 1], ys[j + 1], pz1), voxel=108, group=ctx.group, name='%s_probe_a%d' % (PREFIX, n), indoor_outdoor_level='0'); n += 1
    lm = A.get('lmres', 'terrain')
    if lm == 'terrain':
        cell = 256
        nx = int((px1 - px0) // cell); ny = int((py1 - py0) // cell)
        occ = np.ones((nx, ny), bool)
        G.lmres_terrain(occ, px0, py0, cell, A['ground'], below=8.0, above=160.0, samples=4, group=ctx.group)
    else:
        for b in lm: G.lmres_box(b, group=ctx.group)
    return n


def hints(ctx, A):
    sx0, sy0, sz0, sx1, sy1, sz1 = A['shell']
    whole = (min(sx0, CACHE[0] - CACHE_W) - 256, min(sy0, -CACHE_D) - 256, BOOTH[2] - 512, max(sx1, CACHE[0] + CACHE_W) + 256, max(sy1, CACHE_D) + 256, sz1 + 256)
    G.hint(whole, 'Lowest', group=ctx.group)
    for b, kind in A.get('hints', []): G.hint(b, kind, group=ctx.group)


# ---------------------------------------------------------------- gameplay entities
def gameplay(ctx, A):
    for pid, pos, radius in A['points']:
        ctx.target('%s_point_%s' % (PREFIX, pid), (pos[0], pos[1], pos[2] + 8))
    for team in ('t', 'ct', 'ffa'):
        for i, (x, y, z, yaw) in enumerate(A['drops'][team]):
            ctx.target('%s_drop_%s_%d' % (PREFIX, team, i + 1), (x, y, z), yaw)
    for name, pos in A['landmarks']:
        ctx.target('%s_lm_%s' % (PREFIX, name.lower().replace(' ', '_')), (pos[0], pos[1], pos[2] + 8))


# ---------------------------------------------------------------- nav grid + arena.json
def nav_grid(A):
    (bx0, by0, bz0), (bx1, by1, bz1) = A['bounds']
    cell = NAV_CELL
    x0 = math.floor(bx0 / cell) * cell - cell / 2; y0 = math.floor(by0 / cell) * cell - cell / 2
    x0 = -7168.0; y0 = -7168.0            # INTERFACES section 2: x0/y0 -7168, 56 x 56 cells of 256 cover the 14000 bounds with a margin
    w = h = 56
    xs = x0 + (np.arange(w) + 0.5) * cell; ys = y0 + (np.arange(h) + 0.5) * cell
    X, Y = np.meshgrid(xs, ys, indexing='ij')                 # [ix, iy]
    Z = np.asarray(A['ground'](X, Y), float)
    solid = np.asarray(A['solid'](X, Y), bool) if A.get('solid') else np.zeros(X.shape, bool)
    # slope: ground sampled at the cell's 4 half-offsets
    hs = cell * 0.5
    zs = [np.asarray(A['ground'](X + dx, Y + dy), float) for dx, dy in ((hs, 0), (-hs, 0), (0, hs), (0, -hs))]
    zmin = np.minimum.reduce(zs + [Z]); zmax = np.maximum.reduce(zs + [Z])
    walk = (~solid) & ((zmax - zmin) < 300.0) & (X > bx0 + 200) & (X < bx1 - 200) & (Y > by0 + 200) & (Y < by1 - 200) & (Z > bz0 + 1)
    if A.get('walk_ok') is not None: walk &= np.asarray(A['walk_ok'](X, Y), bool)
    # struct: within 2 cells of any structure footprint
    struct = np.zeros(X.shape, bool)
    for (fx0, fy0, fx1, fy1) in A['struct']:
        struct |= (X > fx0 - 2 * cell) & (X < fx1 + 2 * cell) & (Y > fy0 - 2 * cell) & (Y < fy1 + 2 * cell)
    # cover: of 16 neighbour samples (8 directions x 1 and 2 cells) how many are >= 250 higher or solid
    cnt = np.zeros(X.shape, int)
    for d in (1, 2):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            zn = np.asarray(A['ground'](X + dx * d * cell, Y + dy * d * cell), float)
            sn = np.asarray(A['solid'](X + dx * d * cell, Y + dy * d * cell), bool) if A.get('solid') else False
            cnt += ((zn >= Z + 250.0) | sn).astype(int)
    cover = np.clip(np.round(cnt * 255.0 / 16.0), 0, 255).astype(int)
    order = lambda a: a.T.reshape(-1).tolist()              # idx = iy * w + ix (y-major rows of x)
    return dict(cell=cell, x0=x0, y0=y0, w=w, h=h, order='idx = iy * w + ix', height=[int(round(v)) for v in order(Z)], walk=[int(v) for v in order(walk)],
                struct=[int(v) for v in order(struct)], cover=order(cover)), dict(walk=int(walk.sum()), struct=int(struct.sum()), cells=w * h)


def write_arena_json(A, nav, booth_pos, cache_pos, path):
    import names as N
    (bx0, by0, bz0), (bx1, by1, bz1) = A['bounds']
    j = dict(id=N.ARENA, name=N.ARENAS[N.ARENA], title=N.TITLE, bounds=dict(min=[bx0, by0, bz0], max=[bx1, by1, bz1]),
             drops={k: [[round(v, 1) for v in d] for d in A['drops'][k]] for k in ('t', 'ct', 'ffa')},
             points=[dict(id=pid, pos=[round(v, 1) for v in pos], radius=radius) for pid, pos, radius in A['points']],
             booth=list(booth_pos), cache=list(cache_pos), nav=nav,
             landmarks=[dict(name=n, pos=[round(v, 1) for v in p]) for n, p in A['landmarks']])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(j, open(path, 'w'), separators=(',', ':'))
    return j


# ---------------------------------------------------------------- pictures
def relief(A, box, size=1024, sun=(0.6, -0.5, 0.62)):
    """shaded top-down picture of ground() over box (x0, y0, x1, y1): north (+y) up"""
    x0, y0, x1, y1 = box
    xs = np.linspace(x0, x1, size); ys = np.linspace(y1, y0, size)
    X, Y = np.meshgrid(xs, ys, indexing='xy')
    Z = np.asarray(A['ground'](X, Y), float)
    Zt = np.asarray(A['relief_height'](X, Y), float) if A.get('relief_height') else Z      # shade the terrain, draw structures flat on top
    step = (x1 - x0) / size
    dzdx = np.gradient(Zt, axis=1) / step; dzdy = -np.gradient(Zt, axis=0) / step
    n = np.stack([-dzdx, -dzdy, np.ones_like(Zt)], -1); n /= np.linalg.norm(n, axis=-1, keepdims=True)
    s = np.asarray(sun, float); s /= np.linalg.norm(s)
    shade = np.clip(n @ s, 0, 1) * 0.75 + 0.25
    if A.get('radar_zones'):
        col = np.asarray(A['radar_zones'](X, Y, Z), float)
    else:
        t = (Z - Z.min()) / max(1.0, Z.max() - Z.min())
        col = np.stack([0.35 + 0.5 * t, 0.3 + 0.4 * t, 0.25 + 0.3 * t], -1)
    img = col * shade[..., None]
    built = Z > Zt + 1.0                                     # decks, bridges, podiums: flat light grey, lighter the higher
    if built.any():
        t = np.clip((Z - Zt) / 1500.0, 0, 1)[..., None]
        img = np.where(built[..., None], np.array([0.5, 0.5, 0.52]) * (0.8 + 0.4 * t), img)
    solid = np.asarray(A['solid'](X, Y), bool) if A.get('solid') else None
    if solid is not None: img = np.where(solid[..., None], img * 0.7 + 0.05, img)
    return Image.fromarray(np.clip(img * 255, 0, 255).astype(np.uint8))


def font(sz):
    from PIL import ImageFont
    for p in ('C:/Windows/Fonts/impact.ttf', 'C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def slides(A, rel_img, preview_path, title):
    """4 loading slides (title, controls, modes, tips): drawn by tools/loading_art.py from textured mech renders; the arena pictures are no longer used"""
    import loading_art
    return loading_art.slides(title)
