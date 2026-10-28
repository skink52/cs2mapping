"""Stage C step / stage D pass `steam`: env_steam (and env_steamjet) doesn't exist in CS2. Each one becomes an info_particle_system playing
particles/port_steam/<name>.vpcf, built from its own keyvalues the way Source 1's C_SteamJet draws it: particles live JetLength/Speed
seconds, leave along the entity's forward axis at Speed with +-SpreadSpeed sideways, grow StartSize -> EndSize, spin at +-rollspeed,
fade in and out, renderamt alpha, rendercolor when Emissive (spawnflag 1, self-illuminated) or light grey otherwise. Type 1 (heat wave)
becomes a refracting sprite with a generated soft normal map (a shimmer, no visible steam).
Entities the importer kept are converted in place; env_steams found only in the VMF are added. InitialState -> start_active,
TurnOn/TurnOff inputs -> Start/Stop. Particle names carry the values, so one file serves every jet with the same settings.
Idea from github.com/Ninja-Chris/cs2-slop-porting (env_steam particles), written fresh for this pipeline.
"""
import os, re, io, math

HDR = '<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:vpcf1:version{d47d07e6-072c-49cb-9718-5bfd8d6c3d21} -->\n'
CLASSES = ('env_steam', 'env_steamjet')
KEYS = ('Speed', 'SpreadSpeed', 'StartSize', 'EndSize', 'Rate', 'JetLength', 'rollspeed', 'renderamt', 'rendercolor', 'spawnflags', 'type', 'InitialState')
DEFAULTS = {'speed': 120, 'spreadspeed': 15, 'startsize': 10, 'endsize': 25, 'rate': 26, 'jetlength': 80, 'rollspeed': 8, 'renderamt': 255,
            'spawnflags': 0, 'type': 0, 'initialstate': 0}
UNLIT = (200, 200, 200)

def _f(kv, k):
    try: return float(str(kv.get(k.lower(), DEFAULTS[k.lower()])).split()[0])
    except (ValueError, IndexError): return float(DEFAULTS[k.lower()])

def _col(kv):
    try: return tuple(max(0, min(255, int(float(x)))) for x in str(kv.get('rendercolor', '255 255 255')).split()[:3])
    except ValueError: return (255, 255, 255)

def particle_name(kv):
    n = lambda v: ('%g' % v).replace('.', 'd').replace('-', 'm')
    r, g, b = _col(kv)
    return 'steam_s%s_p%s_z%s_%s_r%s_j%s_l%s_a%d_c%02x%02x%02x_e%d_t%d' % (
        n(_f(kv, 'Speed')), n(_f(kv, 'SpreadSpeed')), n(_f(kv, 'StartSize')), n(_f(kv, 'EndSize')), n(_f(kv, 'Rate')), n(_f(kv, 'JetLength')),
        n(_f(kv, 'rollspeed')), int(_f(kv, 'renderamt')), r, g, b, int(_f(kv, 'spawnflags')) & 1, int(_f(kv, 'type')) == 1)

def vpcf(kv, tex):
    speed = max(_f(kv, 'Speed'), 1.0); spread = _f(kv, 'SpreadSpeed'); rate = max(_f(kv, 'Rate'), 0.1)
    life = max(0.05, _f(kv, 'JetLength') / speed)
    r0 = max(_f(kv, 'StartSize'), 1.0) * 0.5; scale = max(_f(kv, 'EndSize'), 1.0) / max(_f(kv, 'StartSize'), 1.0)
    roll = abs(_f(kv, 'rollspeed')); alpha = int(max(0, min(255, _f(kv, 'renderamt'))))
    emissive = int(_f(kv, 'spawnflags')) & 1; heat = int(_f(kv, 'type')) == 1
    r, g, b = (255, 255, 255) if heat else (_col(kv) if emissive else UNLIT)
    if heat:
        rend = '\t\t\tm_bRefract = true\n\t\t\tm_flRefractAmount = 0.25\n\t\t\tm_nRefractBlurRadius = 1\n'
        roll = 120.0
    else:
        rend = '\t\t\tm_flSelfIllumAmount = 1.0\n' if emissive else ''
    return HDR + '''{
	_class = "CParticleSystemDefinition"
	m_nMaxParticles = %(maxp)d
	m_ConstantColor = [ %(r)d, %(g)d, %(b)d, %(a)d ]
	m_flConstantRadius = %(r0).2f
	m_Renderers =
	[
		{
			_class = "C_OP_RenderSprites"
			m_bAdditive = false
%(rend)s			m_hTexture = resource:"%(tex)s"
		},
	]
	m_Emitters =
	[
		{
			_class = "C_OP_ContinuousEmitter"
			m_flEmitRate = %(rate).2f
		},
	]
	m_Initializers =
	[
		{
			_class = "C_INIT_CreateWithinSphere"
			m_fRadiusMin = 0.0
			m_fRadiusMax = 0.0
			m_LocalCoordinateSystemSpeedMin = [ %(speed).1f, %(nspread).1f, %(nspread).1f ]
			m_LocalCoordinateSystemSpeedMax = [ %(speed).1f, %(spread).1f, %(spread).1f ]
		},
		{
			_class = "C_INIT_RandomLifeTime"
			m_fLifetimeMin = %(life).3f
			m_fLifetimeMax = %(life).3f
		},
		{
			_class = "C_INIT_RandomRotation"
		},
		{
			_class = "C_INIT_RandomRotationSpeed"
			m_flDegreesMin = 0.0
			m_flDegreesMax = %(roll).1f
			m_bRandomlyFlipDirection = true
		},
	]
	m_Operators =
	[
		{
			_class = "C_OP_BasicMovement"
		},
		{
			_class = "C_OP_SpinUpdate"
		},
		{
			_class = "C_OP_InterpolateRadius"
			m_flStartScale = 1.0
			m_flEndScale = %(scale).3f
		},
		{
			_class = "C_OP_FadeInSimple"
			m_flFadeInTime = 0.5
		},
		{
			_class = "C_OP_FadeOutSimple"
			m_flFadeOutTime = 0.5
		},
		{
			_class = "C_OP_Decay"
		},
	]
}
''' % dict(maxp=int(rate * life) + 8, r=r, g=g, b=b, a=alpha, r0=r0, rend=rend, tex=tex, rate=rate, speed=speed, spread=spread, nspread=-spread,
           life=life, roll=roll, scale=scale)

def _png(img):
    b = io.BytesIO(); img.save(b, 'PNG'); return b.getvalue()

def puff_png():
    from PIL import Image
    import numpy as np
    n = 64; y, x = np.mgrid[0:n, 0:n]; d = np.hypot((x + .5) / n - .5, (y + .5) / n - .5) * 2
    a = (np.clip(1 - d, 0, 1) ** 1.5 * 255).astype(np.uint8)
    img = np.dstack([np.full((n, n), 255, np.uint8)] * 3 + [a])
    return _png(Image.fromarray(img, 'RGBA'))

def heat_png():
    """soft rippled tangent-space normal map that flattens to (0,0,1) at the rim, alpha fading to 0 there"""
    from PIL import Image
    import numpy as np
    n = 128; y, x = np.mgrid[0:n, 0:n]; u = (x + .5) / n * 2 - 1; v = (y + .5) / n * 2 - 1
    rng = np.random.RandomState(11)
    h = sum(rng.uniform(.4, 1) * np.sin(rng.uniform(5, 14) * u + rng.uniform(5, 14) * v + rng.uniform(0, 6.3)) for _ in range(7))
    rr = np.clip(np.hypot(u, v), 0, 1); env = (1 - rr) ** 2 * (1 + 2 * rr)
    h = h * env * 2.5
    gy, gx = np.gradient(h); nz = np.ones_like(h); ln = np.sqrt(gx ** 2 + gy ** 2 + 1)
    rgb = np.dstack([(-gx / ln * .5 + .5), (-gy / ln * .5 + .5), (nz / ln * .5 + .5)]) * 255
    a = ((1 - rr ** 2) ** 2 * 255)
    return _png(Image.fromarray(np.dstack([rgb, a]).round().astype(np.uint8), 'RGBA'))

def vtex(png_rel, linear=False):
    import radar
    v = radar.VTEX.replace('panorama/images/overheadmaps/%(map)s_radar_psd.png', png_rel).replace('"int" "1024"', '"int" "128"')
    return v.replace('"srgb"', '"linear"') if linear else v

def vmf_steams(vmfpath):
    import vmf as vmfmod
    if not vmfpath or not os.path.exists(vmfpath): return []
    root = vmfmod.parse(open(vmfpath, encoding='utf-8', errors='replace').read())
    out = []
    for e in root.ch:
        if e.name == 'entity' and (e.get('classname') or '').lower() in CLASSES:
            kv = {k.lower(): e.get(k) for k in KEYS if e.get(k) is not None}
            out.append((e.get('targetname') or '', [float(x) for x in (e.get('origin') or '0 0 0').split()[:3]],
                        [float(x) for x in (e.get('angles') or '0 0 0').split()[:3]], kv))
    return out

def run(m, c, vmfpath=None):
    ents = m.by_class(*CLASSES)
    jobs = []
    for e in ents:
        kv = {a[0].decode().lower(): a[2].decode('utf-8', 'replace') for a in m.props(e)['attrs'] if isinstance(a[2], bytes)}
        jobs.append((e, kv))
    if not ents:
        for name, org, ang, kv in vmf_steams(vmfpath):
            e = m.new_entity('info_particle_system', org, {'targetname': name} if name else {}, angles=ang)
            jobs.append((e, kv))
    if not jobs: return
    made, names = {}, set()
    for e, kv in jobs:
        heat = int(_f(kv, 'type')) == 1
        tex = 'materials/port_steam/heatwave_normal.vtex' if heat else 'materials/port_steam/steam_puff.vtex'
        pn = particle_name(kv)
        if pn not in made: made[pn] = vpcf(kv, tex); c.write('particles/port_steam/%s.vpcf' % pn, made[pn])
        m.setp(e, 'classname', 'info_particle_system')
        m.setp(e, 'effect_name', 'particles/port_steam/%s.vpcf' % pn)
        m.setp(e, 'start_active', '1' if int(_f(kv, 'initialstate')) else '0')
        lk = set(k.lower() for k in KEYS)
        m.props(e)['attrs'] = [a for a in m.props(e)['attrs'] if a[0].decode().lower() not in lk]
        if m.name(e): names.add(m.name(e).lower())
        if heat and 'materials/port_steam/heatwave_normal.png' not in c.files:
            c.write('materials/port_steam/heatwave_normal.png', heat_png())
            c.write('materials/port_steam/heatwave_normal.vtex', vtex('materials/port_steam/heatwave_normal.png', linear=True))
        if not heat and 'materials/port_steam/steam_puff.png' not in c.files:
            c.write('materials/port_steam/steam_puff.png', puff_png())
            c.write('materials/port_steam/steam_puff.vtex', vtex('materials/port_steam/steam_puff.png'))
    remap = {'turnon': 'Start', 'turnoff': 'Stop'}
    fixed = 0; odd = set()
    import dmx
    for _, cc in m.all_conns():
        if dmx.get(cc, b'targetName').decode().lower() not in names: continue
        inp = dmx.get(cc, b'inputName').decode()
        if inp.lower() in remap: dmx.set_(cc, b'inputName', dmx.T_STR, remap[inp.lower()].encode()); fixed += 1
        elif inp.lower() not in ('start', 'stop', 'kill', 'setparent', 'clearparent'): odd.add('%s -> %s' % (dmx.get(cc, b'targetName').decode(), inp))
    c.log.append('%d env_steam -> info_particle_system (%d particle%s in particles/port_steam, %s%d TurnOn/TurnOff inputs -> Start/Stop)'
                 % (len(jobs), len(made), '' if len(made) == 1 else 's', 'added from the VMF, ' if not ents else '', fixed))
    c.todo.append('check the env_steam particles in game (direction along the entity forward axis, size, density%s)'
                  % (', heat-wave refraction' if any('_t1' in p for p in made) else ''))
    if odd: c.todo.append('env_steam inputs with no info_particle_system equivalent (Toggle, Rate, JetLength...): %s' % ', '.join(sorted(odd))[:400])
