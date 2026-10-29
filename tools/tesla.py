"""Stage D pass `tesla`: point_tesla (gone in CS2) -> info_particle_system with a generated crackle particle.

particles/port_tesla/tesla_<rrggbb>.vpcf: short-lived additive sparks scattered through the tesla's radius plus a flickering core,
coloured from m_Color. Inputs aimed at the tesla: TurnOn / DoSpark -> Start, TurnOff -> Stop. Its spark sound isn't carried over.
"""
import os
import dmx

HDR = '<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:vpcf1:version{d47d07e6-072c-49cb-9718-5bfd8d6c3d21} -->\n'
VPCF = HDR + '''{
	_class = "CParticleSystemDefinition"
	m_nMaxParticles = 96
	m_ConstantColor = [ %(r)d, %(g)d, %(b)d, 255 ]
	m_Renderers =
	[
		{
			_class = "C_OP_RenderSprites"
			m_bAdditive = true
			m_hTexture = resource:"materials/port_tesla/spark.vtex"
		},
	]
	m_Emitters =
	[
		{
			_class = "C_OP_ContinuousEmitter"
			m_flEmitRate = 160.0
		},
	]
	m_Initializers =
	[
		{
			_class = "C_INIT_CreateWithinSphere"
			m_fRadiusMin = 0.0
			m_fRadiusMax = %(rad).1f
			m_fSpeedMin = 0.0
			m_fSpeedMax = %(spd).1f
		},
		{
			_class = "C_INIT_RandomRadius"
			m_flRadiusMin = %(smin).1f
			m_flRadiusMax = %(smax).1f
		},
		{
			_class = "C_INIT_RandomLifeTime"
			m_fLifetimeMin = 0.05
			m_fLifetimeMax = 0.18
		},
	]
	m_Operators =
	[
		{
			_class = "C_OP_Decay"
		},
		{
			_class = "C_OP_BasicMovement"
		},
		{
			_class = "C_OP_FadeOutSimple"
			m_flFadeOutTime = 0.5
		},
	]
}
'''


def _texture(c):
    import io
    from PIL import Image
    import radar
    N = 32
    im = Image.new('RGBA', (N, N))
    for y in range(N):
        for x in range(N):
            d = (((x + .5) / N - .5) ** 2 + ((y + .5) / N - .5) ** 2) ** .5 * 2
            a = int(max(0.0, 1 - d) ** 3 * 255 + .5)
            im.putpixel((x, y), (255, 255, 255, a))
    b = io.BytesIO(); im.save(b, 'PNG')
    c.write('materials/port_tesla/spark.png', b.getvalue())
    v = radar.VTEX.replace('panorama/images/overheadmaps/%(map)s_radar_psd.png', 'materials/port_tesla/spark.png').replace('"int" "1024"', '"int" "32"')
    c.write('materials/port_tesla/spark.vtex', v.encode())


def run(m, c):
    tes = m.by_class('point_tesla')
    if not tes: return 0
    names = {}
    for e in tes:
        col = [int(float(x)) for x in (m.P(e, 'm_Color') or '255 255 255').split()[:3]]
        h = '%02x%02x%02x' % tuple(col)
        rad = float(m.P(e, 'm_flRadius') or 200)
        thick = float(m.P(e, 'thick_max') or 8)
        c.write('particles/port_tesla/tesla_%s.vpcf' % h,
                (VPCF % dict(r=col[0], g=col[1], b=col[2], rad=rad * 0.6, spd=rad * 2, smin=thick * 0.5, smax=thick * 1.5)).encode())
        name = m.name(e)
        m.new_entity('info_particle_system', m.origin(e), {'targetname': name, 'effect_name': 'particles/port_tesla/tesla_%s.vpcf' % h,
                                                         'start_active': '0'})
        names[name.lower()] = name
        m.remove_node(e)
    _texture(c)
    n = 0
    for e, cn in m.all_conns():
        t = dmx.get(cn, b'targetName').decode()
        if t.lower() in names:
            i = dmx.get(cn, b'inputName').decode().lower()
            new = {'turnon': b'Start', 'dospark': b'Start', 'turnoff': b'Stop'}.get(i)
            if new: dmx.set_(cn, b'inputName', dmx.T_STR, new); n += 1
    c.log.append('tesla: %d point_tesla (not in CS2) -> info_particle_system with particles/port_tesla crackle particles (%s); %d TurnOn/TurnOff/DoSpark inputs -> Start/Stop'
                 % (len(tes), ', '.join(sorted(names.values())), n))
    return len(tes)
