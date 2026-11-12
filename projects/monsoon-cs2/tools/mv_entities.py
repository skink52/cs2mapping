"""mg_monsoon script entities (stage 5): every name in docs/CONTRACT.md. Positions come from layout.py and from what mv_places.py
actually built (W.sites: kit stations, flag poles, mounts, racks, boards, pads, tunnel mouths, platform tops).

Also the bot navigation markup: WALKABLESEED seeds at the bases, flags and roads, NONAV boxes over steep slopes, karst, deep
river reaches (fords stay open) and everything outside the playable band, so the nav mesh stays small (mg_trenchwarfare's
44k-area nav cost FPS). nav_markup(box, prop, name) writes one func_nav_markup with its closed toolsnavattribute box.

Writes out/world_sites.json for tools/check_world.py (platform tops, tunnel floor samples, listed off-ground props, spawn list).
"""
import os, json, math
import numpy as np
import vmaplib, vmesh, vmapgen as G
from vmaplib import ent, polymesh, box_faces
import layout as L
import mv_stock as S
import mv_models as M
import mv_places as PL

BOOM = 'particles/explosions_fx/explosion_basic.vpcf'
DIRT_FX = 'particles/ambient_fx/impact_dirt.vpcf'
DUST = 'particles/ambient_fx/copter_land_loop_1_dust_low.vpcf'
FX = lambda n: 'models/mv/fx/mv_%s/mv_%s.vmdl' % (n, n)
# models the script may SetModel to (uniforms): add paths to out/cache_models.json (a list) when the player models are copied in
CACHE_DEFAULT = [S.mv('rocket_122'), S.mv('shell_105_dyn')]            # + the crash hulks (mv_models.static('wreck_*'))


def nav_markup(box, prop='NONAV', name='', group=''):
    """func_nav_markup over box (x0, y0, z0, x1, y1, z1): prop = WALKABLESEED (a seed just above a floor), NONAV, NONAVNONSOLID
    or NONAVSPACE. The closed toolsnavattribute box is its child mesh."""
    kw = dict(targetname=name) if name else {}
    e = ent('func_nav_markup', (0, 0, 0), group=group, navProperty_NavGen=prop, flags='1', **kw)
    v, faces = box_faces(*box, inward=False)
    e.attr('children')[2].append(vmaplib.mesh_node(polymesh(v, faces, [G.NAVATTR] * 6, scale=1.0), group, attach=False))
    return e


def blocked(W, x, y, z, r=17.0, h=80.0):
    """something solid recorded by the placer inside a player-sized box here (keep-out discs do not count)"""
    f = dict(c=(x, y), h=(r, r), a=0.0, z=(z + 2.0, z + h), model='probe')
    seen = set()
    for k in W.PL._keys(f):
        for idx in W.PL.grid.get(k, ()):
            if idx in seen: continue
            seen.add(idx); g = W.PL.items[idx]
            if g['model'].startswith('keepout/'): continue
            if W.PL.overlap(f, g): return True
    return False


def stand(W, x, y, tries=((0, 0), (40, 0), (-40, 0), (0, 40), (0, -40), (60, 60), (-60, 60), (60, -60), (-60, -60), (100, 0), (-100, 0), (0, 100), (0, -100),
                          (150, 0), (-150, 0), (0, 150), (0, -150))):
    """a clear spot to stand at or near (x, y): -> (x, y, z of the surface)"""
    for dx, dy in tries:
        px, py = x + dx, y + dy
        z = max(PL.surf_z(px, py), W.T.surf_z(px, py, pad=16.0))
        if not blocked(W, px, py, z) and float(L.slope(px, py)) < 30.0: return px, py, z
    print('WARNING no clear standing spot near (%.0f, %.0f)' % (x, y))
    return x, y, PL.surf_z(x, y)


def build(d, group, out, T, clone):
    W = PL.W
    S_ = W.sites
    n = {}
    def E(cls, pos, ang=(0, 0, 0), **kw):
        n[cls] = n.get(cls, 0) + 1
        return ent(cls, pos, ang, group=group, **kw)
    def dyn(name, model, pos, yaw=0.0, solid='0', pitch=0.0, **kw):
        return E('prop_dynamic', pos, (pitch, yaw, 0), targetname=name, model=model, solid=solid, disableshadows='0', rendercolor='255 255 255',
                 skin='default', **kw)
    def snd(name, pos, event, start='0'):
        return E('point_soundevent', pos, targetname=name, soundName=event, startOnSpawn=start, toLocalPlayer='0', stopOnNew='0', saveAndRestore='0')
    def fx(name, pos, effect):
        return E('info_particle_system', pos, targetname=name, effect_name=effect, start_active='0')
    spawn_log = []
    def tele(name, x, y, yaw):
        px, py, z = stand(W, x, y)
        spawn_log.append([name, px, py, z])
        return E('info_teleport_destination', (px, py, z + 8.0), (0, yaw, 0), targetname=name)

    fb = L.firebase(); cp = L.camp()
    apache = json.load(open(os.path.join(os.path.dirname(os.path.abspath(out)), 'apache.json'))) if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(out)), 'apache.json')) else {}
    nose = float(apache.get('nose_yaw', -90.0))
    # ---------------------------------------------------------------- base spawns, kit stations
    for tg, plan in (('ct', fb), ('t', cp)):
        c = plan['rack']
        for k, p in enumerate(plan['spawns']):
            tele('mv_spawn_%s_%d' % (tg, k + 1), p[0], p[1], math.degrees(math.atan2(p[1] - c[1], p[0] - c[0])))
        kx, ky, kz = S_['kit'][tg]
        E('info_target', (kx, ky, kz + 30.0), targetname='mv_kit_' + tg)
    # ---------------------------------------------------------------- flags
    for l, name, c in L.FLAGS:
        px, py, pz, pyaw = S_['flagpole'][l]
        E('info_target', (px, py, pz), targetname='mv_flag_' + l)
        dyn('mv_flagpole_' + l, S.mv('flag_pole'), (px, py, pz), pyaw, solid='6')
        snd('mv_flag_snd_' + l, (px, py, pz + 120.0), 'mv.capture')
        for k, p in enumerate(L.flag_spawns(l)):
            tele('mv_flagspawn_%s_%d' % (l, k + 1), p[0], p[1], math.degrees(math.atan2(c[1] - p[1], c[0] - p[0])) + 180.0)
        if l in S_['kit']:
            kx, ky, kz = S_['kit'][l]
            E('info_target', (kx, ky, kz + 24.0), targetname='mv_kit_' + l)
    # ---------------------------------------------------------------- helicopters on their pads
    for tg, plan in (('ct', fb), ('t', cp)):
        yaw = plan['pad_yaw']
        for k, (px, py, pz) in enumerate(S_['pads'][tg]):
            i = k + 1
            E('info_target', (px, py, pz), (0, yaw, 0), targetname='mv_pad_%s_%d' % (tg, i))
            wreck = M.static('wreck_' + tg); wyaw = 90.0 if M.is_ext(wreck) else 0.0
            if tg == 'ct':
                dyn('mv_heli_ct_%d' % i, S.APACHE['model'], (px, py, pz), yaw + nose, solid='6', DefaultAnim=apache.get('default_anim', 'idle'))
                dyn('mv_wreck_ct_%d' % i, wreck, (-600.0 + 700.0 * k, 600.0, L.PARK_Z), wyaw, solid='6')
            else:
                h = M.pick(M.HELI_ON_PAD['t'][k])                 # body + the two rotor props on their hubs (model table)
                dyn('mv_heli_t_%d' % i, h['body'], (px, py, pz), yaw, solid='6')
                mx, my = PL.local(px, py, yaw, h['hub'][0], h['hub'][1])
                dyn('mv_rotor_t_%d' % i, h['rotor'], (mx, my, pz + h['hub'][2]), yaw + 25.0 * k)
                tx, ty = PL.local(px, py, yaw, h['tail_hub'][0], h['tail_hub'][1])
                dyn('mv_tail_t_%d' % i, h['tail'], (tx, ty, pz + h['tail_hub'][2]), yaw)
                dyn('mv_wreck_t_%d' % i, wreck, (-600.0 + 700.0 * k, 1400.0, L.PARK_Z), wyaw, solid='6')
            for nm, ev in (('eng', 'mv.heli_rotor'), ('gun', 'mv.heli_gun'), ('gun2', 'mv.heli_gun'), ('rkt', 'mv.rocket_launch')):
                snd('mv_heli_%s_%s_%d' % (nm, tg, i), (px, py, pz + 120.0), ev)
            fx('mv_heli_smoke_%s_%d' % (tg, i), (px, py, pz + 150.0), PL.SMOKE_DARK)
            fx('mv_heli_dust_%s_%d' % (tg, i), (px, py, pz + 4.0), DUST)
    # ---------------------------------------------------------------- batteries: carriage, elevating part, racks, board
    for tg, kind, ev in (('ct', 'howitzer', 'mv.howitzer_fire'), ('t', 'rocket', 'mv.rocket_fire')):
        g = M.pick(kind); tr = g['trunnion']; rest = g['rest_pitch']
        for k, (gx, gy, gz_, yaw) in enumerate(S_['guns'][tg]):
            i = k + 1
            dyn('mv_gun_%s_%d' % (tg, i), g['carriage'], (gx, gy, gz_), yaw, solid='6')
            tx, ty = PL.local(gx, gy, yaw, tr[0], tr[1])
            dyn('mv_tube_%s_%d' % (tg, i), g['tube'], (tx, ty, gz_ + tr[2]), yaw, pitch=rest)
            if 'round' in g: dyn('mv_round_t_%d' % i, g['round'], (tx, ty, gz_ + tr[2] + g['round_up']), yaw, pitch=rest)
            snd('mv_gun_snd_%s_%d' % (tg, i), (gx, gy, gz_ + 60.0), ev)
            mz = tr[0] + g['muzzle']
            fx('mv_gun_fx_%s_%d' % (tg, i), (gx + mz * math.cos(math.radians(yaw)), gy + mz * math.sin(math.radians(yaw)), gz_ + tr[2] + 14.0), DIRT_FX)
            rx, ry, rz = S_['racks'][tg][k]
            E('info_target', (rx, ry, rz + 30.0), targetname='mv_rack_%s_%d' % (tg, i))
        b = S_['board'][tg]
        E('info_target', (b['pos'][0], b['pos'][1], b['pos'][2] + 40.0), (0, b['yaw'], 0), targetname='mv_board_' + tg)
        for k in range(len(S_['guns'][tg])):
            s = b['seats'][k]
            tele('mv_boardseat_%s_%d' % (tg, k + 1), s[0], s[1], math.degrees(math.atan2(b['pos'][1] - s[1], b['pos'][0] - s[0])))
    # ---------------------------------------------------------------- mounted guns
    for k, m in enumerate(S_['mounts']):
        i = k + 1; x, y, z = m['pos']
        dyn('mv_mount_%d' % i, M.pick(m['kind'])['gun'], (x, y, z), m['yaw'])
        tele('mv_mountseat_%d' % i, m['seat'][0], m['seat'][1], m['yaw'])
        snd('mv_mount_snd_%d' % i, (x, y, z + 10.0), 'mv.mount_gun')
        E('info_target', (x, y, z + 20.0), (0, m['yaw'], 0), targetname='mv_mountinfo_%d' % i, message='%s:%s' % (m['kind'], m['team']))
    json.dump([dict(n=k + 1, kind=m['kind'], team=m['team'], x=round(m['pos'][0], 1), y=round(m['pos'][1], 1), z=round(m['pos'][2], 1), yaw=round(m['yaw'] % 360.0, 1))
               for k, m in enumerate(S_['mounts'])], open(os.path.join(os.path.dirname(os.path.abspath(out)), 'mounts.json'), 'w'), indent=1)
    # ---------------------------------------------------------------- pools, parked at PARK_Z
    pz = L.PARK_Z
    for k in range(16):
        p = (-700.0 + 90.0 * k, -400.0, pz)
        fx('mv_boom_fx_%d' % (k + 1), p, BOOM); fx('mv_dirt_fx_%d' % (k + 1), (p[0], p[1] + 30, pz), DIRT_FX)
        snd('mv_boom_snd_%d' % (k + 1), (p[0], p[1] + 60, pz), 'mv.shell_impact'); snd('mv_whistle_snd_%d' % (k + 1), (p[0], p[1] + 90, pz), 'mv.shell_whistle')
        E('env_shake', (p[0], p[1] + 120, pz), targetname='mv_shake_%d' % (k + 1), amplitude='7', radius='1000', duration='1.3', frequency='40', spawnflags='0')
        dyn('mv_rocket_%d' % (k + 1), FX('rocket'), (p[0], p[1] + 200, pz))
    for k in range(24): dyn('mv_tracer_%d' % (k + 1), FX('tracer'), (-700.0 + 60.0 * k, 0.0, pz))
    for k in range(10): dyn('mv_marker_%d' % (k + 1), FX('mission_ring'), (-700.0 + 260.0 * (k % 5), 300.0 + 300.0 * (k // 5), pz - 400.0))
    for k in range(6): fx('mv_smoke_fx_%d' % (k + 1), (-700.0 + 90.0 * k, -700.0, pz), PL.SMOKESTACK)
    for k in range(12): dyn('mv_pip_%d' % (k + 1), FX('gunpip'), (-700.0 + 150.0 * k, -900.0, pz))
    for k in range(12): dyn('mv_shell_%d' % (k + 1), S.mv('shell_105_dyn'), (-700.0 + 60.0 * k, -1100.0, pz))
    cj = os.path.join(os.path.dirname(os.path.abspath(out)), 'cache_models.json')
    cache = [M.static('wreck_t'), M.static('wreck_ct')] + list(CACHE_DEFAULT) + (json.load(open(cj)) if os.path.exists(cj) else [])
    for k, m in enumerate(dict.fromkeys(cache)):
        dyn('mv_cache_%d' % (k + 1), m, (-700.0 + 120.0 * (k % 12), -1500.0 - 120.0 * (k // 12), pz))
    snd('mv_ambience', (0.0, 0.0, L.LOBBY_Z + 200.0), 'mv.amb.valley', start='1')
    for k, (x, y, z) in enumerate(S_['tunnels']):
        n['info_teleport_destination'] = n.get('info_teleport_destination', 0) + 1
        ent('info_teleport_destination', (x, y, z + 8.0), group=group, targetname='mv_tunnel_%d' % (k + 1))
    # ---------------------------------------------------------------- navigation
    seeds = 0
    for (x, y) in S_['seeds']:
        x, y, z = stand(W, x, y)
        nav_markup((x - 40, y - 40, z + 2, x + 40, y + 40, z + 34), 'WALKABLESEED', 'mv_nav_seed_%d' % (seeds + 1), group); seeds += 1
    for (x, y, z) in S_.get('plat_seed', []):
        nav_markup((x - 40, y - 40, z + 2, x + 40, y + 40, z + 34), 'WALKABLESEED', 'mv_nav_seed_%d' % (seeds + 1), group); seeds += 1
    for (x, y, z) in S_['tunnels'][:1]:
        nav_markup((x - 24, y - 24, z + 2, x + 24, y + 24, z + 34), 'WALKABLESEED', 'mv_nav_seed_%d' % (seeds + 1), group); seeds += 1
    nonav = nonav_boxes(W)
    for k, b in enumerate(nonav): nav_markup(b, 'NONAV', 'mv_nav_no_%d' % (k + 1), group)
    n['func_nav_markup'] = seeds + len(nonav)
    json.dump(dict(surfaces=S_['surfaces'], exceptions=W.exc, spawns=spawn_log, nonav=[list(map(float, b)) for b in nonav],
                   tunnel=dict(samples=PL.tunnel_plan()['samples'].tolist(), floor=PL.tunnel_plan()['floor'].tolist(), chamber=list(L.TUNNEL_CHAMBER) + [L.TUNNEL_CHAMBER_R, PL.tunnel_plan()['f_ch']]),
                   mounts=len(S_['mounts']), karst=[dict(x=k['x'], y=k['y'], r=k['r'], top=k['top']) for k in W.karst], waypoints=S_.get('waypoints', []),
                   landing=S_.get('landing', [])),
              open(os.path.join(os.path.dirname(os.path.abspath(out)), 'world_sites.json'), 'w'))
    print('entities:', ', '.join('%s %d' % kv for kv in sorted(n.items())), '| mounts %d, nav seeds %d, NONAV boxes %d' % (len(S_['mounts']), seeds, len(nonav)))


def nonav_boxes(W, cell=256.0):
    """NONAV boxes: grid cells that are too steep, under a karst tower, deep river (fords near the bridge and the paddies stay open)
    or outside the playable band; merged into rectangles. Cells over the tunnels and the bases stay navigable."""
    X0, Y0 = -L.MAP_X - 256.0, -L.MAP_Y - 256.0
    nx = int((2 * L.MAP_X + 512) / cell); ny = int((2 * L.MAP_Y + 512) / cell)
    f = (np.arange(5) + 0.5) / 5 * cell
    ox, oy = np.meshgrid(f, f, indexing='ij')
    X = X0 + np.arange(nx)[:, None, None, None] * cell + ox[None, None]; Y = Y0 + np.arange(ny)[None, :, None, None] * cell + oy[None, None]
    X, Y = np.broadcast_arrays(X, Y)
    Z = L.height(X, Y); SL = L.slope(X, Y)
    CX = X.mean((2, 3)); CY = Y.mean((2, 3))
    steep = (SL > 40.0).mean((2, 3)) > 0.6
    water = (Z < L.WATER_Z - 8.0).mean((2, 3)) > 0.7
    ford = ((CX > 100.0) & (CX < 620.0)) | (np.abs(CX + 2650.0) < 260.0) | (CX > L.MARSH_X0 - 200.0)
    base = (np.hypot(CX - L.CT_BASE[0], CY - L.CT_BASE[1]) < L.CT_FOOT_R + 200.0) | (np.hypot(CX - L.T_BASE[0], CY - L.T_BASE[1]) < L.T_FOOT_R + 200.0)
    far = (L.water_dist(CX, CY) > 3500.0) & ~base
    edge = (np.abs(CX) > L.MAP_X) | (np.abs(CY) > L.MAP_Y)
    karst = L.karst_dist(CX, CY) < -cell * 0.45
    bridge = (np.abs(CX - L.BRIDGE_X) < cell * 0.5 + 110.0) & (np.abs(CY - L.BRIDGE_Y) < L.BRIDGE_LEN / 2 + L.BRIDGE_RAMP + cell * 0.5)
    water &= ~ford & ~bridge                 # 12 Nov review: the river boxes swallowed the bridge deck (bots could not cross)
    no = steep | water | far | edge | karst
    wateronly = water & ~(steep | far | edge | karst)
    t = PL.tunnel_plan()['box']
    no &= ~((CX > t[0] - cell) & (CX < t[3] + cell) & (CY > t[1] - cell) & (CY < t[4] + cell) & ~karst)
    zlo = Z.min((2, 3)); zhi = Z.max((2, 3))
    done = np.zeros(no.shape, bool); out = []
    for i in range(nx):
        for j in range(ny):
            if not no[i, j] or done[i, j]: continue
            j1 = j
            while j1 + 1 < ny and no[i, j1 + 1] and not done[i, j1 + 1] and j1 + 1 - j < 8: j1 += 1
            i1 = i
            while i1 + 1 < nx and no[i1 + 1, j:j1 + 1].all() and not done[i1 + 1, j:j1 + 1].any() and i1 + 1 - i < 8: i1 += 1
            done[i:i1 + 1, j:j1 + 1] = True
            ztop = float(zhi[i:i1 + 1, j:j1 + 1].max()) + 260.0
            if wateronly[i:i1 + 1, j:j1 + 1].all(): ztop = L.WATER_Z + 30.0          # river cells: nothing above the water is closed
            out.append((X0 + i * cell, Y0 + j * cell, float(zlo[i:i1 + 1, j:j1 + 1].min()) - 48.0, X0 + (i1 + 1) * cell, Y0 + (j1 + 1) * cell, ztop))
    return out
