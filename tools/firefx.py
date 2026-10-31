"""env_fire (doesn't burn in CS2: seen on ttt_minecraft and ba_jail_keimusho) -> info_particle_system with a generated fire particle.

particles/port_fire/fire_<size>.vpcf: additive flame sprites rising from a disc of radius ~0.3 x firesize, white-yellow fading to deep red,
plus a few slower embers, all from one generated soft flame texture (materials/port_fire/flame.png). The entity keeps its name and is
pitched -90 so the particle's local forward axis points up. Inputs: StartFire -> Start, Extinguish / ExtinguishTemporary / Disable ->
Stop; Enable (allow starting) has no particle equivalent and is dropped. The fire's damage was never the entity's job on these maps
(separate trigger_hurts); a fire with damagescale > 0 is listed in TO CHECK.
    firefx.run(m, c)
From ba_jail_keimusho (31 Oct 2026)."""
import io, math
import numpy as np
from PIL import Image
import dmx

HDR = '<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:vpcf1:version{d47d07e6-072c-49cb-9718-5bfd8d6c3d21} -->\n'
VPCF = HDR + '''{
	_class = "CParticleSystemDefinition"
	m_nMaxParticles = %(maxp)d
	m_ConstantColor = [ 255, 214, 120, 255 ]
	m_flConstantRadius = %(r0).1f
	m_Renderers =
	[
		{
			_class = "C_OP_RenderSprites"
			m_bAdditive = true
			m_flSelfIllumAmount = 1.0
			m_hTexture = resource:"materials/port_fire/flame.vtex"
		},
	]
	m_Emitters =
	[
		{
			_class = "C_OP_ContinuousEmitter"
			m_flEmitRate = %(rate).1f
		},
	]
	m_Initializers =
	[
		{
			_class = "C_INIT_CreateWithinSphere"
			m_fRadiusMin = 0.0
			m_fRadiusMax = %(disc).1f
			m_LocalCoordinateSystemSpeedMin = [ %(vmin).1f, -12.0, -12.0 ]
			m_LocalCoordinateSystemSpeedMax = [ %(vmax).1f, 12.0, 12.0 ]
		},
		{
			_class = "C_INIT_RandomLifeTime"
			m_fLifetimeMin = 0.35
			m_fLifetimeMax = 0.8
		},
		{
			_class = "C_INIT_RandomRadius"
			m_flRadiusMin = %(rmin).1f
			m_flRadiusMax = %(rmax).1f
		},
		{
			_class = "C_INIT_RandomRotation"
		},
		{
			_class = "C_INIT_RandomRotationSpeed"
			m_flDegreesMin = 0.0
			m_flDegreesMax = 90.0
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
			_class = "C_OP_ColorInterpolate"
			m_ColorFade = [ 190, 40, 8, 255 ]
		},
		{
			_class = "C_OP_InterpolateRadius"
			m_flStartScale = 1.0
			m_flEndScale = 0.35
		},
		{
			_class = "C_OP_FadeInSimple"
			m_flFadeInTime = 0.15
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
'''

def _flame_png():
    N = 64
    y, x = np.mgrid[0:N, 0:N] / (N - 1.0)
    cx = x - 0.5; cy = y - 0.62                         # teardrop: wide at the bottom, pointed at the top
    w = 0.32 * np.clip(1 - (0.62 - y) * 1.1, 0.15, 1.0)
    d = np.sqrt((cx / np.maximum(w, 1e-3)) ** 2 + (cy / 0.45) ** 2)
    rng = np.random.RandomState(7)
    n = Image.fromarray((rng.rand(16, 16) * 255).astype(np.uint8)).resize((N, N), Image.BICUBIC)
    noise = np.asarray(n, np.float32) / 255.0
    a = np.clip(1 - d, 0, 1) ** 1.4 * (0.75 + 0.5 * noise)
    a = np.clip(a, 0, 1)
    rgba = np.zeros((N, N, 4), np.uint8); rgba[..., :3] = 255; rgba[..., 3] = (a * 255).astype(np.uint8)
    b = io.BytesIO(); Image.fromarray(rgba, 'RGBA').save(b, 'PNG'); return b.getvalue()

def run(m, c):
    fires = m.by_class('env_fire')
    if not fires: return 0
    import radar
    c.write('materials/port_fire/flame.png', _flame_png())
    c.write('materials/port_fire/flame.vtex', radar.VTEX.replace('panorama/images/overheadmaps/%(map)s_radar_psd.png', 'materials/port_fire/flame.png')
            .replace('"int" "1024"', '"int" "64"').encode())
    names = {}; sizes = set(); hot = []
    for e in fires:
        size = max(16, int(round(float(m.P(e, 'firesize', '64') or 64) / 16.0) * 16))
        sizes.add(size)
        sf = int(float(m.P(e, 'spawnflags', '0') or 0))
        on = bool(sf & 4) and (m.P(e, 'StartDisabled', '0') or '0') == '0'
        try:
            if float(m.P(e, 'damagescale', '0') or 0) > 0: hot.append(m.name(e) or 'unnamed')
        except ValueError: pass
        name = m.name(e)
        o = m.origin(e)
        m.new_entity('info_particle_system', o, {'targetname': name, 'effect_name': 'particles/port_fire/fire_%d.vpcf' % size,
                                                 'start_active': '1' if on else '0'}, angles=(-90, 0, 0))
        if name: names[name.lower()] = name
        m.remove_node(e)
    for s in sizes:
        c.write('particles/port_fire/fire_%d.vpcf' % s, (VPCF % dict(maxp=int(s * 0.9) + 16, r0=s * 0.2, rate=s * 0.9, disc=s * 0.3,
                                                                    vmin=s * 0.6, vmax=s * 1.3, rmin=s * 0.15, rmax=s * 0.28)).encode())
    nin = ndrop = 0
    MAP = {'startfire': b'Start', 'extinguish': b'Stop', 'extinguishtemporary': b'Stop', 'disable': b'Stop'}
    for e in m.entities():
        a = dmx.geta(m.E[e], b'connectionsData')
        if not a: continue
        keep = []
        for ci in a[2]:
            cc = m.E[ci]
            t = dmx.get(cc, b'targetName').decode().lower(); i = dmx.get(cc, b'inputName').decode().lower()
            if t in names and i == 'enable': ndrop += 1; continue
            if t in names and i in MAP: dmx.set_(cc, b'inputName', dmx.T_STR, MAP[i]); nin += 1
            keep.append(ci)
        a[2] = keep
    c.log.append('env_fire: %d -> info_particle_system with generated particles/port_fire/fire_<size>.vpcf (sizes %s); %d StartFire/Extinguish/Disable -> Start/Stop, %d Enable outputs dropped'
                 % (len(fires), sorted(sizes), nin, ndrop))
    if hot: c.todo.append('env_fire with damage (damagescale > 0) now only shows flames: %s' % ', '.join(hot))
    return len(fires)
