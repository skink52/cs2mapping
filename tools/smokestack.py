"""Stage C step / stage D pass `smoke`: Source 1 smoke and mote effects that draw nothing in CS2 -> info_particle_system with a generated
vpcf66 particle under particles/port_smoke/ (never a stock path). Covers what steam.py, firefx.py, tesla.py, spotbeam.py and particles.py don't:

  env_smokestack    Rate puffs a second from a disc of BaseSpread, rising at Speed (+-SpreadSpeed sideways, plus WindSpeed along WindAngle)
                    for JetLength units, StartSize -> EndSize, rendercolor at renderamt, spinning up to `roll` deg/s. InitialState -> start_active.
  func_dustmotes    SpawnRate motes a second anywhere in the brush box, LifetimeMin..Max s, SizeMin..Max, Alpha, Color, drifting up to SpeedMax
  func_dustcloud    (none when Frozen); small motes (SizeMax < 16) doubled and brightened (Source drew a hard dot). StartDisabled -> start_active 0.
  env_embers        density sparks a second in the box, lifetime s, flying along the entity's angles at speed (+-speed/8), self-illuminated.
  func_smokevolume  the box filled with puffs every ParticleSpacingDistance, ParticleDrawWidth wide, Color1..Color2 at Density, turning at
                    RotationSpeed; they stay (no wall fade).
  env_smoketrail    spawnrate puffs a second within spawnradius, minspeed..maxspeed any way plus min..maxdirectedspeed along the angles,
                    startsize -> endsize, startcolor -> endcolor at opacity.
  env_spritetrail   (gone in CS2) 48 additive sprites a second that stay where they were made while the (parented) entity moves on: lifetime s,
                    startwidth -> endwidth, rendercolor x renderamt. Always on, as in Source 1.
Point entities the importer kept are converted in place; brush ones (the importer drops func_dustmotes) are added from the VMF at the box
centre and their meshes removed. Particle names carry a hash of their values, so one file serves every entity with the same values.
TurnOn/TurnOff (and Enable/Disable) -> Start/Stop; other inputs are listed. Sprites are a generated soft puff (materials/port_smoke/), not
the map's SmokeMaterial. Rerun-safe: an entity added from the VMF before is not added again.

Parameter formulas from CS2-Porter vmf.py (_smokestack_params, _dustcloud_params, _embers_params, _smokevolume_params,
_smoketrail_params) and its assets/smokestack_template.vpcf / box_sprites_template.vpcf / smoke_template.vpcf (MIT, copyright bcanusar),
adapted to this pipeline's vpcf66 writer; nothing here has been seen in game.
    smokestack.run(m, c, vmfpath)
"""
import hashlib, math, os
import dmx, vmf as vmfmod
import vpcf66 as P

POINT = ('env_smokestack', 'env_smoketrail', 'env_spritetrail')
BRUSH = ('func_dustmotes', 'func_dustcloud', 'env_embers', 'func_smokevolume')
CLASSES = POINT + BRUSH
TEX = 'materials/port_smoke/puff.vtex'
DIR = 'particles/port_smoke'
INPUTS = {'turnon': 'Start', 'turnoff': 'Stop', 'enable': 'Start', 'disable': 'Stop'}
KEEP = {'classname', 'targetname', 'parentname', 'origin', 'angles'}


def _num(kv, k, d):
    try: return float(str(kv.get(k.lower(), d)).split()[0])
    except (ValueError, IndexError): return float(d)


def _rgb(text, d):
    try:
        v = [int(round(float(x))) for x in str(text).split()[:3]]
        return tuple(max(0, min(255, x)) for x in v) if len(v) == 3 else d
    except ValueError: return d


def _wind_world(kv):
    s = _num(kv, 'WindSpeed', 0); a = math.radians(_num(kv, 'WindAngle', 0))
    return (math.cos(a) * s, math.sin(a) * s)


# ---------------------------------------------------------------- vpcf66 building blocks
def _system(maxp, color, radius, rend, emitter, inits, ops, draw=None):
    r, g, b, a = color
    head = ['{', '\t_class = "CParticleSystemDefinition"', '\tm_nBehaviorVersion = 12', '\tm_nMaxParticles = %d' % maxp,
            '\tm_ConstantColor = [ %d, %d, %d, %d ]' % (r, g, b, a), '\tm_flConstantRadius = %s' % P.f(radius)]
    if draw: head.append('\tm_flMaxDrawDistance = %s' % P.f(draw))
    return P.HDR + '\n'.join(head + ['\tm_Renderers =', '\t['] + rend + ['\t]', '\tm_Emitters =', '\t['] + emitter + ['\t]',
                                     '\tm_Initializers =', '\t['] + inits + ['\t]', '\tm_Operators =', '\t['] + ops + ['\t]', '}']) + '\n'


def _continuous(rate): return P.op('C_OP_ContinuousEmitter', m_flEmitRate='%.3f' % rate)


def _instant(n):
    ind = '\t\t\t'
    return ['\t\t{', ind + '_class = "C_OP_InstantaneousEmitter"', ind + 'm_nParticlesToEmit = '] + P.pf(ind, m_flLiteralValue=P.f(n)) + ['\t\t},']


def _box(half):
    ind = '\t\t'
    out = [ind + '{', ind + '\t_class = "C_INIT_CreateWithinBox"', ind + '\tm_vecMin = ']
    out += P.pvec(ind + '\t', [-h for h in half]); out += [ind + '\tm_vecMax = '] + P.pvec(ind + '\t', half)
    return out + [ind + '\tm_bLocalSpace = false', ind + '},']


def _velocity(vmin, vmax):
    ind = '\t\t'
    out = [ind + '{', ind + '\t_class = "C_INIT_VelocityRandom"', ind + '\tm_LocalCoordinateSystemSpeedMin = ']
    out += P.pvec(ind + '\t', vmin); out += [ind + '\tm_LocalCoordinateSystemSpeedMax = '] + P.pvec(ind + '\t', vmax)
    return out + [ind + '},']


def _disc(r):
    ind = '\t\t'
    out = [ind + '{', ind + '\t_class = "C_INIT_CreateWithinSphereTransform"', ind + '\tm_fRadiusMax = ']
    out += P.pf(ind + '\t', m_flLiteralValue=P.f(r))
    return out + [ind + '\tm_vecDistanceBias = [ 1.0, 1.0, 0.0 ]', ind + '},']


def _color(lo, hi=None):
    hi = hi or lo
    return P.op('C_INIT_RandomColor', m_ColorMin='[ %d, %d, %d, 255 ]' % tuple(lo), m_ColorMax='[ %d, %d, %d, 255 ]' % tuple(hi))


def _ops(end_scale=1.0, t_in=0.2, t_out=0.5, color_end=None, drag=0.0):
    o = P.op('C_OP_BasicMovement', **({'m_fDrag': P.f(drag)} if drag else {})) + P.op('C_OP_SpinUpdate')
    if abs(end_scale - 1.0) > 1e-3:
        o += P.op('C_OP_InterpolateRadius', m_flStartTime='0.0', m_flEndTime='1.0', m_flStartScale='1.0', m_flEndScale='%.4f' % end_scale)
    if color_end: o += P.op('C_OP_ColorInterpolate', m_ColorFade='[ %d, %d, %d, 255 ]' % tuple(color_end))
    return o + P.fade(t_in, t_out) + P.op('C_OP_Decay')


def _alpha(a): return P.init_float(a, a, P.ALPHA)          # alpha attribute is 0..1


# ---------------------------------------------------------------- one particle per class (CS2-Porter's formulas)
def smokestack_vpcf(kv):
    speed = max(_num(kv, 'Speed', 30), 0.1); side = max(_num(kv, 'SpreadSpeed', 15), 0.0); start = max(_num(kv, 'StartSize', 20), 0.5)
    wx, wy = _wind_world(kv); life = min(max(_num(kv, 'JetLength', 180), 1.0) / speed, 30.0); rate = max(_num(kv, 'Rate', 20), 0.1)
    alpha = min(max(_num(kv, 'renderamt', 255) / 255.0, 0.0), 1.0); roll = abs(_num(kv, 'roll', 0))
    inits = _disc(max(_num(kv, 'BaseSpread', 20), 0.0)) + P.init_float(life, life, P.LIFE) + P.init_float(start, start, P.RADIUS) + \
        P.init_float(0, 360, P.ROT) + P.init_float(0, roll, P.ROTSPEED, True) + _alpha(alpha) + _color(_rgb(kv.get('rendercolor'), (255, 255, 255))) + \
        _velocity((wx - side, wy - side, speed), (wx + side, wy + side, speed))
    rend = P.renderer(TEX, extra=['m_nFeatheringMode = "PARTICLE_DEPTH_FEATHERING_ON_OPTIONAL"'])
    return _system(min(int(rate * life * 1.25) + 16, 5000), (255, 255, 255, 255), start, rend, _continuous(rate), inits,
                   _ops(max(_num(kv, 'EndSize', 30), 0.0) / start))


def dust_vpcf(kv, size, cls):
    half = [max(s / 2.0, 1.0) for s in size]
    draw = max(5000.0, round(0.5 * math.sqrt(sum(s * s for s in size)) + 3000.0))
    if cls == 'env_embers':
        speed = max(_num(kv, 'speed', 32), 0.0); sd = speed / 8.0; life = max(_num(kv, 'lifetime', 4), 0.1); rate = max(_num(kv, 'density', 50), 1.0)
        inits = _box(half) + P.init_float(life, life, P.LIFE) + P.init_float(2, 3, P.RADIUS) + _color(_rgb(kv.get('rendercolor'), (255, 255, 255))) + \
            _velocity((speed - sd, -sd, -sd), (speed + sd, sd, sd))
        rend = P.renderer(TEX, additive=True, selfillum=1.0)
        return _system(min(int(rate * life * 1.25) + 16, 5000), (255, 255, 255, 255), 2.5, rend, _continuous(rate), inits, _ops(0.0, 0.05, 1.0), draw)
    if cls == 'func_smokevolume':
        sp = max(_num(kv, 'ParticleSpacingDistance', 80), 8.0); counts = [max(1, round(s / sp)) for s in size]
        n = min(counts[0] * counts[1] * counts[2], 2000); rad = max(_num(kv, 'ParticleDrawWidth', 120), 1.0) / 2.0
        c1 = _rgb(kv.get('color1'), (255, 255, 255)); c2 = _rgb(kv.get('color2'), (255, 255, 255))
        inits = _box(half) + P.init_float(3600, 3600, P.LIFE) + P.init_float(rad * 0.9, rad * 1.1, P.RADIUS) + P.init_float(0, 360, P.ROT) + \
            P.init_float(0, abs(_num(kv, 'RotationSpeed', 10)), P.ROTSPEED, True) + _alpha(min(max(_num(kv, 'Density', 1), 0.0), 1.0)) + \
            _color([min(a, b) for a, b in zip(c1, c2)], [max(a, b) for a, b in zip(c1, c2)])
        rend = P.renderer(TEX, extra=['m_nFeatheringMode = "PARTICLE_DEPTH_FEATHERING_ON_OPTIONAL"'])
        return _system(n + 8, (255, 255, 255, 255), rad, rend, _instant(n), inits, _ops(1.0, 0.5, 0.01), draw)
    # func_dustmotes / func_dustcloud (C_Func_Dust)
    speed = 0.0 if str(kv.get('frozen', '0')).strip() == '1' else max(_num(kv, 'SpeedMax', 13), 0.0)
    lo, hi = sorted((max(_num(kv, 'LifetimeMin', 3), 0.1), max(_num(kv, 'LifetimeMax', 5), 0.1)))
    smin, smax = sorted((max(_num(kv, 'SizeMin', 100), 0.5), max(_num(kv, 'SizeMax', 200), 0.5)))
    small = smax < 16.0; a = _num(kv, 'Alpha', 30) / 255.0
    alpha = min(max(a * 4.0, 0.4) if small else max(a, 0.01), 1.0); k = 2.0 if small else 1.0; rate = max(_num(kv, 'SpawnRate', 40), 1.0)
    inits = _box(half) + P.init_float(lo, hi, P.LIFE) + P.init_float(smin * k, smax * k, P.RADIUS) + P.init_float(0, 360, P.ROT) + _alpha(alpha) + \
        _color(_rgb(kv.get('color'), (255, 255, 255))) + _velocity((-speed,) * 3, (speed,) * 3)
    rend = P.renderer(TEX, extra=['m_nFeatheringMode = "PARTICLE_DEPTH_FEATHERING_ON_OPTIONAL"'])
    return _system(min(int(rate * hi * 1.25) + 16, 5000), (255, 255, 255, 255), smax * k, rend, _continuous(rate), inits, _ops(1.0, 0.3, 0.4), draw)


def smoketrail_vpcf(kv):
    start = max(_num(kv, 'startsize', 15), 1.0); lo, hi = sorted((max(_num(kv, 'minspeed', 10), 0.0), max(_num(kv, 'maxspeed', 20), 0.0)))
    dlo, dhi = sorted((_num(kv, 'mindirectedspeed', 0), _num(kv, 'maxdirectedspeed', 0))); life = max(_num(kv, 'lifetime', 5), 0.1)
    rate = max(_num(kv, 'spawnrate', 20), 0.1); c0 = _rgb(kv.get('startcolor'), (192, 192, 192)); c1 = _rgb(kv.get('endcolor'), (160, 160, 160))
    inits = P.sphere((dlo - hi, -hi, -hi), (dhi + hi, hi, hi), rmax=max(_num(kv, 'spawnradius', 15), 0.0)) + P.init_float(life, life, P.LIFE) + \
        P.init_float(start, start, P.RADIUS) + P.init_float(0, 360, P.ROT) + P.init_float(0, 20, P.ROTSPEED, True) + \
        _alpha(min(max(_num(kv, 'opacity', 0.75), 0.0), 1.0)) + _color(c0)
    rend = P.renderer(TEX, extra=['m_nFeatheringMode = "PARTICLE_DEPTH_FEATHERING_ON_OPTIONAL"'])
    return _system(min(int(rate * life * 1.25) + 16, 5000), (255, 255, 255, 255), start, rend, _continuous(rate), inits,
                   _ops(max(_num(kv, 'endsize', 50), 0.0) / start, 0.2, 0.5, c1))


def spritetrail_vpcf(kv):
    life = max(_num(kv, 'lifetime', 0.5), 0.05); w0 = max(_num(kv, 'startwidth', 8), 0.5); w1 = max(_num(kv, 'endwidth', 1), 0.0)
    a = min(max(_num(kv, 'renderamt', 255) / 255.0, 0.0), 1.0)
    col = [int(round(x * a)) for x in _rgb(kv.get('rendercolor'), (255, 255, 255))]      # additive: a lower alpha is a darker colour
    inits = P.sphere() + P.init_float(life, life, P.LIFE) + P.init_float(w0 / 2, w0 / 2, P.RADIUS) + _color(col)
    ops = P.op('C_OP_Decay') + P.op('C_OP_InterpolateRadius', m_flStartTime='0.0', m_flEndTime='1.0', m_flStartScale='1.0', m_flEndScale='%.4f' % (w1 / w0)) +         P.op('C_OP_FadeOutSimple', m_flFadeOutTime='0.6')
    return _system(int(48 * life) + 16, (255, 255, 255, 255), w0 / 2, P.renderer(TEX, additive=True, selfillum=1.0), _continuous(48), inits, ops)


def particle(cls, kv, size=None):
    if cls == 'env_spritetrail': text = spritetrail_vpcf(kv)
    elif cls == 'env_smokestack': text = smokestack_vpcf(kv)
    elif cls == 'env_smoketrail': text = smoketrail_vpcf(kv)
    else: text = dust_vpcf(kv, size, cls)
    kind = cls.split('_', 1)[1]
    return '%s/%s_%s.vpcf' % (DIR, kind, hashlib.sha1(text.encode()).hexdigest()[:10]), text


def start_active(cls, kv):
    if cls == 'env_smokestack': return str(kv.get('initialstate', '0')).strip() == '1'
    if cls == 'env_embers': return int(_num(kv, 'spawnflags', 0)) & 1 == 1
    if cls in ('func_dustmotes', 'func_dustcloud'): return str(kv.get('startdisabled', '0')).strip() != '1'
    if cls == 'env_spritetrail': return True
    return True


# ---------------------------------------------------------------- VMF side
def _bounds(e):
    import re
    pts = [[float(v) for v in p.split()] for s in e.ch if s.name == 'solid' for sd in s.ch if sd.name == 'side'
           for p in re.findall(r'\(([^)]*)\)', sd.get('plane') or '')]
    pts = [p for p in pts if len(p) == 3]
    if not pts: return None
    return [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]


def vmf_effects(vmfpath):
    if not vmfpath or not os.path.exists(vmfpath): return []
    with open(vmfpath, encoding='utf-8', errors='replace') as fh: root = vmfmod.parse(fh.read())
    out = []
    for e in root.ch:
        cls = (e.get('classname') or '').lower() if e.name == 'entity' else ''
        if cls not in CLASSES: continue
        kv = {k.lower(): v for k, v in e.kv}
        b = _bounds(e) if cls in BRUSH else None
        if cls in BRUSH and b is None: continue
        org = [(b[0][k] + b[1][k]) / 2 for k in range(3)] if b else [float(x) for x in (e.get('origin') or '0 0 0').split()[:3]]
        out.append((cls, kv, org, [float(x) for x in (e.get('angles') or '0 0 0').split()[:3]], [b[1][k] - b[0][k] for k in range(3)] if b else None))
    return out


# ---------------------------------------------------------------- map side
def _kv(m, e): return {a[0].decode().lower(): a[2].decode('utf-8', 'replace') for a in m.props(e)['attrs'] if isinstance(a[2], bytes)}


def run(m, c, vmfpath=None):
    jobs = []                                   # (entity node, class, kv, size)
    have = {cls: m.by_class(cls) for cls in CLASSES}
    done = [(m.origin(e), m.P(e, 'effect_name', '')) for e in m.by_class('info_particle_system') if (m.P(e, 'effect_name', '') or '').startswith(DIR + '/')]
    for cls in CLASSES:
        for e in have[cls]:
            size = None
            if cls in BRUSH:
                b = m.bounds(e)
                if b is None: continue
                size = [b[1][k] - b[0][k] for k in range(3)]
                ctr = [(b[0][k] + b[1][k]) / 2 for k in range(3)]
                kids = dmx.geta(m.E[e], b'children'); kids[2] = [x for x in kids[2] if m.type(x) != b'CMapMesh']
                dmx.set_(m.E[e], b'origin', dmx.T_V3, [float(x) for x in ctr])
            jobs.append((e, cls, _kv(m, e), size))
    added = 0
    for cls, kv, org, ang, size in vmf_effects(vmfpath):
        if have[cls]: continue                  # the importer kept this class: converted in place above
        kind = cls.split('_', 1)[1]
        if any(eff.startswith('%s/%s_' % (DIR, kind)) and max(abs(o[k] - org[k]) for k in range(3)) < 1.0 for o, eff in done): continue
        props = {'targetname': kv['targetname']} if kv.get('targetname') else {}
        if kv.get('parentname'): props['parentname'] = kv['parentname']
        e = m.new_entity('info_particle_system', org, props, angles=ang if cls in ('env_embers', 'env_smoketrail') else (0, 0, 0))
        jobs.append((e, cls, kv, size)); added += 1
    if not jobs: return 0
    made = {}; names = set(); by_cls = {}
    for e, cls, kv, size in jobs:
        rel, text = particle(cls, kv, size)
        if rel not in made: made[rel] = text; c.write(rel, text)
        m.setp(e, 'classname', 'info_particle_system'); m.setp(e, 'effect_name', rel)
        m.setp(e, 'start_active', '1' if start_active(cls, kv) else '0')
        if cls == 'env_smokestack': dmx.set_(m.E[e], b'angles', dmx.T_QANG, [0.0, 0.0, 0.0])   # rises along world z; wind is world yaw
        m.props(e)['attrs'] = [a for a in m.props(e)['attrs'] if a[0].decode().lower() in KEEP | {'effect_name', 'start_active'}]
        if m.name(e): names.add(m.name(e).lower())
        by_cls[cls] = by_cls.get(cls, 0) + 1
    if 'materials/port_smoke/puff.png' not in c.files:
        import steam
        c.write('materials/port_smoke/puff.png', steam.puff_png()); c.write('materials/port_smoke/puff.vtex', steam.vtex('materials/port_smoke/puff.png'))
    fixed = 0; odd = set()
    for _, cc in m.all_conns():
        if (dmx.get(cc, b'targetName') or b'').decode('utf-8', 'replace').lower() not in names: continue
        inp = dmx.get(cc, b'inputName').decode()
        if inp.lower() in INPUTS: dmx.set_(cc, b'inputName', dmx.T_STR, INPUTS[inp.lower()].encode()); fixed += 1
        elif inp.lower() not in ('start', 'stop', 'kill', 'setparent', 'clearparent', 'setparentattachment', 'destroyimmediately'):
            odd.add('%s -> %s' % (dmx.get(cc, b'targetName').decode('utf-8', 'replace'), inp))
    c.log.append('smoke: %s -> info_particle_system (%d particle%s in %s; %d added from the VMF; %d TurnOn/TurnOff/Enable/Disable -> Start/Stop)'
                 % (', '.join('%d %s' % (v, k) for k, v in sorted(by_cls.items())), len(made), '' if len(made) == 1 else 's', DIR, added, fixed))
    c.todo.append('smoke: check the converted %s in game (density, size, colour; generated soft puff instead of the map\'s smoke material)' % ', '.join(sorted(by_cls)))
    if odd: c.todo.append('smoke: inputs with no info_particle_system equivalent (Toggle, Rate, JetLength ...): %s' % ', '.join(sorted(odd))[:400])
    return len(jobs)
