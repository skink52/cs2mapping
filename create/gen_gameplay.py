"""Gameplay setup: competitive plans (defuse / hostage / wingman) with spawn grids, buyzones, bomb sites and timings; game modes (deathmatch,
arms race, aim, surf, bhop, kz) with their convars; movement-course pieces (surf ramps, bhop platforms, start / finish zones).

  plan = competitive('defuse', anchors={'t': (x, y, z), 'ct': (...), 'a': (...), 'b': (...)}, paths={'t-a': [(x, y), ...], ...})
       -> {'spawns': {2: [...], 3: [...]}, 'buyzones': {2: box, 3: box}, 'sites': {'a': box, ...}, 'hostages': [...], 'rescue': box,
           'timings': {'t-a': {'units', 'knife_s', 'rifle_s'}, ...}, 'balance': [...warnings]}
     (wingman: one site 'a', 2 + 2 spawns; hostage: hostages at 'b' (or 'a'), rescue zone at the CT spawn)
  place_competitive(plan, group)                 entities + buyzone / site / rescue brushes into the vmaplib map
  mode_config(mode, **overrides) -> mechkit "mode" config {name, commands, give};  MODES[mode]['launch'] = the game_type / game_mode line
  surf_ramp(start_xy, end_xy, z_top, width=256, height=256, angle=50)   bhop_platforms(start_xyz, count, gap=160, size=64, rise=0)
  course_zones(start_box, finish_box, name='kz')  -> trigger shapes wired to mechkit's race minigame (<name>_cp_0 / _cp_1)
Timings use cs2-map-mcp's rule of thumb: CT should reach each site 5-10 s before T (knife 250 u/s, rifle 215 u/s).

Ported from competitive.py (add_comp_plan, timings), modes.py (mode_setup, add_surf_ramp, add_bhop_platforms, add_movement_course) of
cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT). Fresh code; their bot-round playtests are live-game (autoport's part).
"""
import math
import primitives as P

KNIFE, RIFLE = 250.0, 215.0
MODES = {
    'casual':     {'launch': 'game_type 0; game_mode 0', 'commands': []},
    'wingman':    {'launch': 'game_type 0; game_mode 2', 'commands': []},
    'deathmatch': {'launch': 'game_type 1; game_mode 2', 'commands': ['mp_respawn_on_death_t 1', 'mp_respawn_on_death_ct 1', 'mp_buy_anywhere 1',
                                                                      'mp_respawn_immunitytime 2', 'mp_teammates_are_enemies 1']},
    'armsrace':   {'launch': 'game_type 1; game_mode 0', 'commands': ['mp_respawn_on_death_t 1', 'mp_respawn_on_death_ct 1']},
    'aim':        {'launch': 'game_type 3; game_mode 0', 'commands': ['mp_buy_anywhere 0', 'mp_buytime 0', 'mp_freezetime 0'], 'give': ['weapon_ak47', 'weapon_m4a1_silencer']},
    'surf':       {'launch': 'game_type 3; game_mode 0', 'commands': ['sv_airaccelerate 150', 'sv_staminamax 0', 'sv_falldamage_scale 0',
                                                                    'mp_respawn_on_death_t 1', 'mp_respawn_on_death_ct 1', 'mp_freezetime 0']},
    'bhop':       {'launch': 'game_type 3; game_mode 0', 'commands': ['sv_enablebunnyhopping 1', 'sv_autobunnyhopping 1', 'sv_staminamax 0',
                                                                    'sv_staminajumpcost 0', 'sv_staminalandcost 0', 'sv_falldamage_scale 0', 'mp_freezetime 0']},
    'kz':         {'launch': 'game_type 3; game_mode 0', 'commands': ['sv_staminamax 0', 'sv_falldamage_scale 0', 'mp_respawn_on_death_t 1',
                                                                    'mp_respawn_on_death_ct 1', 'mp_freezetime 0']},
}


def _grid(centre, n, spacing=48.0, height=8.0, cols=None):
    cols = cols or max(1, int(math.ceil(math.sqrt(n))))
    rows = int(math.ceil(n / cols))
    x0 = centre[0] - (cols - 1) * spacing / 2; y0 = centre[1] - (rows - 1) * spacing / 2
    return [[x0 + (i % cols) * spacing, y0 + (i // cols) * spacing, centre[2] + height] for i in range(n)]


def _box_around(points, pad=64.0, zpad=(0.0, 128.0)):
    xs = [p[0] for p in points]; ys = [p[1] for p in points]; zs = [p[2] for p in points]
    return [[min(xs) - pad, min(ys) - pad, min(zs) - 8 - zpad[0]], [max(xs) + pad, max(ys) + pad, max(zs) + zpad[1]]]


def path_length(points):
    return sum(math.dist(a[:2], b[:2]) for a, b in zip(points, points[1:]))


def competitive(kind, anchors, paths=None, per_team=None, site_size=(384, 384, 160)):
    if kind not in ('defuse', 'hostage', 'wingman'): raise ValueError('kind: defuse, hostage or wingman')
    need = {'t', 'ct', 'a'} | ({'b'} if kind == 'defuse' else set())
    if need - set(anchors): raise ValueError('anchors needed: %s' % ', '.join(sorted(need)))
    n = per_team or (2 if kind == 'wingman' else 5)
    spawns = {2: _grid(anchors['t'], n), 3: _grid(anchors['ct'], n)}
    plan = {'kind': kind, 'spawns': spawns, 'buyzones': {t: _box_around(s) for t, s in spawns.items()}, 'sites': {}, 'hostages': [],
            'rescue': None, 'timings': {}, 'balance': []}
    sx, sy, sz = site_size
    if kind in ('defuse', 'wingman'):
        for s in (['a', 'b'] if kind == 'defuse' else ['a']):
            c = anchors[s]; plan['sites'][s] = [[c[0] - sx / 2, c[1] - sy / 2, c[2]], [c[0] + sx / 2, c[1] + sy / 2, c[2] + sz]]
    else:
        h = anchors.get('b', anchors['a'])
        plan['hostages'] = [[h[0] + dx, h[1], h[2] + 8] for dx in (-48, 48)]
        plan['rescue'] = _box_around(spawns[3], 128)
    paths = paths or {}
    for team in ('t', 'ct'):
        for s in ([k for k in ('a', 'b') if k in anchors]):
            key = '%s-%s' % (team, s)
            pts = paths.get(key) or [anchors[team], anchors[s]]
            L = path_length([tuple(p) + (0,) * (3 - len(p)) for p in pts])
            plan['timings'][key] = {'units': round(L), 'knife_s': round(L / KNIFE, 1), 'rifle_s': round(L / RIFLE, 1), 'straight_line': key not in paths}
    for s in [k for k in ('a', 'b') if k in anchors]:
        t, c = plan['timings'].get('t-' + s), plan['timings'].get('ct-' + s)
        if t and c:
            lead = t['knife_s'] - c['knife_s']
            if lead < 5: plan['balance'].append('site %s: CT arrives only %.1f s before T (aim for 5-10 s)' % (s, lead))
            elif lead > 12: plan['balance'].append('site %s: CT arrives %.1f s before T: T can hardly take it' % (s, lead))
    return plan


def place_competitive(plan, group='comp'):
    import mechkit
    nodes = []
    for team, cls in ((2, 'info_player_terrorist'), (3, 'info_player_counterterrorist')):
        for p in plan['spawns'][team]: nodes.append(P.entity(cls, p, (0, 0, 0), group=group, strict=False))
    for team, box in plan['buyzones'].items():
        nodes.append(mechkit._brush_loose('func_buyzone', P.box(box[0], box[1], 'materials/tools/toolstrigger.vmat'), group, {'TeamNum': team}))
    for s, box in plan['sites'].items():
        nodes.append(mechkit._brush_loose('func_bomb_target', P.box(box[0], box[1], 'materials/tools/toolstrigger.vmat'), group, {'targetname': 'site_' + s}))
    for h in plan['hostages']: nodes.append(P.entity('hostage_entity', h, group=group, strict=False))
    if plan['rescue']:
        nodes.append(mechkit._brush_loose('func_hostage_rescue', P.box(plan['rescue'][0], plan['rescue'][1], 'materials/tools/toolstrigger.vmat'), group, {}))
    for team in (2, 3):
        c = plan['spawns'][team][0]
        nodes.append(P.entity('point_nav_walkable', (c[0], c[1], c[2] - 4), group=group, strict=False))
    return nodes


def mode_config(mode, **overrides):
    if mode not in MODES: raise ValueError('mode must be one of %s' % ', '.join(MODES))
    m = MODES[mode]
    cfg = {'name': mode, 'commands': list(m['commands']), 'every_round': True}
    if m.get('give'): cfg['give'] = list(m['give'])
    cfg.update(overrides)
    return cfg


def surf_ramp(start, end, z_top, width=256.0, height=256.0, angle=50.0, mat='materials/dev/reflectivity_50.vmat'):
    """a triangular surf ramp from start to end (axis-aligned line); its two faces slope `angle` degrees (surfable: 45-60)"""
    (sx, sy), (ex, ey) = start, end
    half = height / math.tan(math.radians(angle))
    prof = [(-half, z_top - height), (half, z_top - height), (0.0, z_top)]
    if abs(ey - sy) < 1e-6:
        x0, x1 = sorted((sx, ex))
        return P.extrude([(p[0] + sy, p[1]) for p in prof], x1 - x0, 'yz', (x0, 0, 0), mat)
    if abs(ex - sx) < 1e-6:
        y0, y1 = sorted((sy, ey))
        return P.extrude([(p[0] + sx, p[1]) for p in prof], y1 - y0, 'xz', (0, y0, 0), mat)
    raise ValueError('surf_ramp takes an axis-aligned line')


def bhop_platforms(start, count=8, gap=160.0, size=64.0, rise=0.0, direction=(1, 0), thick=16.0, mat='materials/dev/reflectivity_70.vmat'):
    """a row of small platforms `gap` apart (edge to edge), each `rise` higher than the last"""
    dx, dy = direction; L = math.hypot(dx, dy); dx, dy = dx / L, dy / L
    out = []
    for i in range(count):
        cx = start[0] + dx * i * (size + gap); cy = start[1] + dy * i * (size + gap); z = start[2] + rise * i
        out.append(('bhop_%d' % i, P.box((cx - size / 2, cy - size / 2, z - thick), (cx + size / 2, cy + size / 2, z), mat)))
    return out


def course_zones(start_box, finish_box, name='kz', script='mech', group='course'):
    """start / finish triggers that drive mechkit's race minigame {'kind': 'race', 'name': name, 'checkpoints': 2}"""
    import mechkit
    return [mechkit.trigger(P.box(start_box[0], start_box[1], 'materials/tools/toolstrigger.vmat'), name + '_cp_0', script, 'OnEndTouch', group=group),
            mechkit.trigger(P.box(finish_box[0], finish_box[1], 'materials/tools/toolstrigger.vmat'), name + '_cp_1', script, 'OnStartTouch', group=group)]
