"""mg_monsoon script entities (stage 5): every name in docs/CONTRACT.md. Positions come from layout.py and from what mv_places.py
actually built (W.sites: kit stations, flag poles, mounts, racks, boards, pads, tunnel mouths, platform tops).

Also the bot navigation markup: WALKABLESEED seeds at the bases, flags and roads, NONAV boxes over everything bots do not use
(nav_play_mask: outside the bases, flags, roads, trails, fords and the tunnels; inside them steep slopes, karst and deep river),
so the nav mesh stays small (mg_trenchwarfare's 44k-area nav cost FPS; this map's first compile made 33,661 areas).
tools/check_play.py check 9 estimates the nav from these boxes (`--nav-plan` before a regenerate).
nav_markup(box, prop, name) writes one func_nav_markup with its closed toolsnavattribute box.

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


NAV_MARGIN = 64.0           # nav kept this far beyond a road's / trail's own half width (pass 4: 160 -> 64)
NAV_CELL = 128.0
# pass 3 review (bot nav cost): the first compile made 33,661 nav areas ("Compute Approach areas" 26 min; mg_trenchwarfare lost FPS
# with bots at 44k). Nav is kept only where bots fight and walk: the bases, the five flags and their surroundings, every road and
# trail, two fords and the gully approach from the firebase to the temple's river stair (the CT walking route to D), the farm and
# the tunnels. Everything else (outer valley sides, karst, the marsh, the jungle between the routes, deep river) is NONAV.
# pass 4 review: the compile made 15,033 areas with these at ct_base +100, t_base +150, flag 820, flag_a 650, margin 160. Cut toward
# ~12,000 (check_play --nav-plan on the pass 3 map: 115,469 -> ~91,000 cells): the CT disc ends 40 u past the wire, the T disc 50 u
# inside its plateau edge (its pads, AA pits and hooches are all within r 1000), the flag discs 600 u (capture radius 350, flag spawns
# at 230, cover counted to 600), road margins 64 u. Every station stays on the nav and both bases still route to every flag (check 9).
NAV_ZONES = dict(ct_base=L.CT_PLATEAU_R - 70.0, t_base=L.T_PLATEAU_R - 50.0, flag=600.0, flag_a=600.0, farm=450.0, c123=450.0, portal=420.0,
                 waypoint=160.0, seed=160.0)


def nav_corridors():
    """(polyline, half width) of every walking route bots need beyond the roads: the fords and the CT approach to the temple"""
    ry = lambda x: float(L.river_y(x))
    t = L.TEMPLE
    return [
        # ford west: the camp - river trail on the north bank to the paddies (T's way to flag A)
        ([(-2600.0, ry(-2600.0) + 420.0), (-2650.0, ry(-2650.0)), (-2700.0, ry(-2700.0) + L.PADDY_YR1 - 40.0)], 230.0),
        # out of the firebase gate, down its north-west flank and the gully floodplain, across the river at x 2100-2400 to the temple's
        # west stair (CT's walking route to flag D, check_play 1b; the hill north of the gate is too steep)
        ([(3240.0, -2504.0), (2872.0, -2472.0), (2664.0, -2152.0), (2664.0, -920.0), (2424.0, -200.0), (2136.0, 88.0), (2056.0, 456.0), (2104.0, 840.0),
          (t[0] - 340.0, t[1])], 230.0),
        # pass 3: the branch across the river to the temple's ghat (the flights down from the south stair)
        ([(2424.0, -200.0), (2330.0, 300.0), (t[0] - 200.0, float(L.river_y(t[0])) + 110.0), (t[0], float(L.river_y(t[0])) + 110.0)], 200.0),
    ]


def nav_play_mask(CX, CY, sites=None):
    """True where bots keep nav (see NAV_ZONES / nav_corridors)"""
    m = np.zeros(CX.shape, bool)
    d = lambda p: np.hypot(CX - p[0], CY - p[1])
    m |= d(L.CT_BASE) < NAV_ZONES['ct_base']
    m |= d(L.T_BASE) < NAV_ZONES['t_base']
    for l, _, c in L.FLAGS:
        if l == 'a': continue
        m |= d(c) < NAV_ZONES['flag']
    fa = L.FLAGS[0][2]
    m |= d(fa) < NAV_ZONES['flag_a']
    yr = CY - L.river_y(CX)                                    # the whole paddy field (flag A) and the north-bank paddies
    m |= (CX > L.PADDY_X0 - 150.0) & (CX < L.PADDY_X1 + 150.0) & (yr > L.PADDY_YR0 - 150.0) & (yr < L.PADDY_YR1 + 120.0)
    m |= (CX > L.PADDY2_X0 - 120.0) & (CX < L.PADDY2_X1 + 120.0) & (yr > L.PADDY2_YR0 - 120.0) & (yr < L.PADDY2_YR1 + 120.0)
    m |= d(L.FARM) < NAV_ZONES['farm']
    m |= d(L.C123[:2]) < NAV_ZONES['c123']
    m |= (np.abs(CX - L.BRIDGE_X) < 560.0) & (np.abs(CY - L.BRIDGE_Y) < L.BRIDGE_LEN / 2 + L.BRIDGE_RAMP + 420.0)
    for p in L.TUNNEL_PORTALS: m |= d(p) < NAV_ZONES['portal']
    for hw, pts in L.ROADS:
        dd, _ = L.seg_dist(CX, CY, pts); m |= dd < hw + NAV_MARGIN
    for pts, hw in nav_corridors():
        dd, _ = L.seg_dist(CX, CY, pts); m |= dd < hw
    for (nm, x, y, z) in (sites or {}).get('waypoints', []):
        if 'waterfall' not in nm: m |= d((x, y)) < NAV_ZONES['waypoint']
    for (x, y) in (sites or {}).get('seeds', []): m |= d((x, y)) < NAV_ZONES['seed']
    return m


def tunnel_roof(cell=NAV_CELL):
    """{(i, j) of the nonav grid: highest tunnel ceiling (or open cut) z inside that cell}"""
    t = PL.tunnel_plan(); gx, gy, occ, CZ = t['gx'], t['gy'], t['occ'], t['CZ']
    X0, Y0 = -L.MAP_X - 256.0, -L.MAP_Y - 256.0
    out = {}
    for i, j in zip(*np.nonzero(occ)):
        cz = float(CZ[i:i + 2, j:j + 2].max()) + (400.0 if t['open'][i, j] else 0.0)
        k = (int((gx[i] + 8.0 - X0) // cell), int((gy[j] + 8.0 - Y0) // cell))
        out[k] = max(out.get(k, -1e9), cz)
    return out


def nonav_boxes(W, cell=NAV_CELL, sites=None):
    """NONAV boxes over every grid cell bots do not need (nav_play_mask), and inside the play zones over cells that are too steep,
    under a karst tower or deep river (the fords and the bridge stay open); merged into rectangles. Over the tunnels a box starts
    above the gallery roof, so the galleries keep their nav; a cell where the gallery is open to the sky (portal cuts) stays open.
    W: the World (its sites: seeds, waypoints) or None with `sites` given (tools/check_play.py's estimate)."""
    if sites is None: sites = W.sites if W is not None else {}
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
    ford = ((CX > 100.0) & (CX < 620.0)) | (np.abs(CX + 2650.0) < 260.0)
    route = np.zeros(CX.shape, bool)              # a route keeps its steep cells (nav generation itself skips what is too steep)
    for pts, hw in nav_corridors():
        dd, _ = L.seg_dist(CX, CY, pts); ford |= dd < hw; route |= dd < hw
    for hw, pts in L.ROADS:
        dd, _ = L.seg_dist(CX, CY, pts); route |= dd < hw + 64.0
    steep &= ~route
    edge = (np.abs(CX) > L.MAP_X) | (np.abs(CY) > L.MAP_Y)
    karst = L.karst_dist(CX, CY) < -cell * 0.45
    bridge = (np.abs(CX - L.BRIDGE_X) < cell * 0.5 + 110.0) & (np.abs(CY - L.BRIDGE_Y) < L.BRIDGE_LEN / 2 + L.BRIDGE_RAMP + cell * 0.5)
    play = nav_play_mask(CX, CY, sites)
    water &= ~ford & ~bridge                 # 12 Nov review: the river boxes swallowed the bridge deck (bots could not cross)
    no = ~play | steep | water | edge | karst
    wateronly = water & play & ~(steep | edge | karst)
    zlo = Z.min((2, 3)); zhi = Z.max((2, 3))
    z0c = zlo - 48.0
    zt = zhi + 260.0
    for (kx, ky, kr, kh, ks) in L.KARST:                     # the karst crowns too (bots never get up there)
        zt = np.where(np.hypot(CX - kx, CY - ky) < kr, np.maximum(zt, L.gz(kx, ky) + kh + 320.0), zt)
    # over the tunnels: the box starts above the roof (or the cell stays open where the roof is within 40 u of the ground / cut open)
    tun = np.zeros(no.shape, bool)
    for (i, j), roof in tunnel_roof(cell).items():
        if not (0 <= i < nx and 0 <= j < ny): continue
        tun[i, j] = True
        if roof + 40.0 > zlo[i, j]: no[i, j] = False
        else: z0c[i, j] = max(roof + 12.0, zlo[i, j] - 48.0)
    done = np.zeros(no.shape, bool); out = []
    for i in range(nx):
        for j in range(ny):
            if not no[i, j] or done[i, j]: continue
            kind = (wateronly[i, j], tun[i, j])
            same = lambda a, b: no[a, b] & ~done[a, b] & (wateronly[a, b] == kind[0]) & (tun[a, b] == kind[1])
            j1 = j
            while j1 + 1 < ny and same(i, j1 + 1) and j1 + 1 - j < 15 and not kind[1]: j1 += 1
            i1 = i
            while i1 + 1 < nx and np.all(same(i1 + 1, slice(j, j1 + 1))) and i1 + 1 - i < 15 and not kind[1]: i1 += 1
            done[i:i1 + 1, j:j1 + 1] = True
            ztop = float(zt[i:i1 + 1, j:j1 + 1].max())
            if kind[0]: ztop = L.WATER_Z + 30.0          # river cells: nothing above the water is closed
            out.append((X0 + i * cell, Y0 + j * cell, float(z0c[i:i1 + 1, j:j1 + 1].min()), X0 + (i1 + 1) * cell, Y0 + (j1 + 1) * cell, ztop))
    return out
