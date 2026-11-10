"""Effects for original maps (vmaplib map open with vmapgen.open_map): stock particles, rain / snow over an area, lightning flashes.

  effect(kind, origin, name, start=True)            info_particle_system with a stock CS2 particle (EFFECTS) or any .vpcf path
  precipitation(box, kind='rain', name, start=True)  func_precipitation over the box (toolsprecipitation mesh). CS2's FGD marks the class
                                                     @exclude (fgdcheck: excluded_class), so it may not exist in game: prefer weather_tiles
  weather_tiles(box, kind='rain', name, tile=1024)   a grid of rain / snow particles over the box, switched together by a relay
                                                     (FireUser1 starts, FireUser2 stops): for areas where func_precipitation looks thin
  lightning(name, origin, interval=12, duration=0.25, thunder=None, start=True, alpha=180)
                                                     logic_timer -> env_fade white flash (+ a thunder sound event); FireTimer flashes now;
                                                     alpha 0-255 = flash strength (180 blinds a screen: ~50 for a game)
Returns the entity nodes and the inputs that switch them. Particle names are CS2 stock files (checked against pak01 in the tests where CS2
is installed); custom particles: tools/vpcf66.py, tools/steam.py, tools/firefx.py.

Ported from fx.py of cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT): the effect table, precipitation volume, tiled weather
relay and timer + env_fade lightning. Fresh code on create/primitives.py.
"""
import primitives as P

EFFECTS = {
    'fire_small': 'particles/burning_fx/env_fire_small.vpcf', 'fire_large': 'particles/burning_fx/env_fire_large.vpcf',
    'smoke': 'particles/ambient_fx/ambient_smokestack.vpcf', 'steam': 'particles/maps/de_train/train_steam_leak.vpcf',
    'sparks': 'particles/ambient_fx/env_sparks_omni.vpcf', 'dust': 'particles/ambient_fx/dustmotes_64.vpcf',
    'rain': 'particles/rain_fx/rain.vpcf', 'snow': 'particles/rain_fx/snow.vpcf', 'ash': 'particles/rain_fx/ash.vpcf',
}
PRECIP_MAT = 'materials/tools/toolsprecipitation.vmat'


def _ent(cls, origin, **kv):
    return P.entity(cls, origin, strict=False, **kv)


def effect(kind, origin, name, start=True, group=''):
    path = EFFECTS.get(kind, kind)
    if not path.endswith('.vpcf'): raise ValueError('kind must be one of %s or a .vpcf path' % ', '.join(EFFECTS))
    e = _ent('info_particle_system', origin, group=group, targetname=name, effect_name=path, start_active=int(bool(start)))
    return {'nodes': [e], 'inputs': {'start': (name, 'Start'), 'stop': (name, 'Stop')}, 'particle': path}


def precipitation(box, kind='rain', name='weather', start=True, group=''):
    if kind not in ('rain', 'snow', 'ash'): raise ValueError('kind: rain, snow or ash')
    # CS2's FGD marks func_precipitation @exclude (tools/fgdcheck.py: excluded_class): Hammer hides it and it is unverified in game
    import vmaplib
    e = P.entity('func_precipitation', tuple((box[0][i] + box[1][i]) / 2 for i in range(3)), group=group, strict=False,
                 targetname=name, subclass_name='precipitation_%s' % kind, StartDisabled=int(not start))
    shape = P.box(box[0], box[1], PRECIP_MAT)
    e.attr('children')[2].append(vmaplib.mesh_node(vmaplib.polymesh(*shape), group=group, attach=False))
    return {'nodes': [e], 'inputs': {'start': (name, 'Enable'), 'stop': (name, 'Disable')},
            'warning': 'func_precipitation is @exclude in the CS2 FGD (unverified in game): weather_tiles is the safe choice'}


def weather_tiles(box, kind='rain', name='weather', tile=1024.0, start=True, group=''):
    path = EFFECTS[kind] if kind in EFFECTS else kind
    lo, hi = box
    relay = _ent('logic_relay', (lo[0], lo[1], hi[2]), group=group, targetname=name)
    nodes = [relay]
    nx = max(1, int(round((hi[0] - lo[0]) / tile))); ny = max(1, int(round((hi[1] - lo[1]) / tile)))
    for i in range(nx):
        for j in range(ny):
            x = lo[0] + (i + 0.5) * (hi[0] - lo[0]) / nx; y = lo[1] + (j + 0.5) * (hi[1] - lo[1]) / ny
            t = '%s_%d_%d' % (name, i, j)
            nodes.append(_ent('info_particle_system', (x, y, hi[2]), group=group, targetname=t, effect_name=path, start_active=int(bool(start))))
            P.connect(relay, 'OnUser1', t, 'Start', check_output=False)
            P.connect(relay, 'OnUser2', t, 'Stop', check_output=False)
    return {'nodes': nodes, 'tiles': nx * ny, 'inputs': {'start': (name, 'FireUser1'), 'stop': (name, 'FireUser2')}}


def lightning(name, origin, interval=12.0, duration=0.25, thunder=None, start=True, group='', alpha=180):
    flash = name + '_flash'
    timer = _ent('logic_timer', origin, group=group, targetname=name, StartDisabled=int(not start), RefireTime=interval, UseRandomTime=1,
                 LowerRandomBound=interval * 0.5, UpperRandomBound=interval * 1.5)
    fade = _ent('env_fade', origin, group=group, targetname=flash, spawnflags=1, duration=duration, holdtime=0, renderamt=int(alpha),
                rendercolor='210 225 255')
    P.connect(timer, 'OnTimer', flash, 'Fade', check_output=False)
    nodes = [timer, fade]
    if thunder:
        snd = _ent('point_soundevent', origin, group=group, targetname=name + '_thunder', soundName=thunder)
        P.connect(timer, 'OnTimer', name + '_thunder', 'StartSound', delay=1.5, check_output=False)
        nodes.append(snd)
    return {'nodes': nodes, 'inputs': {'start': (name, 'Enable'), 'stop': (name, 'Disable'), 'flash': (name, 'FireTimer')}}
