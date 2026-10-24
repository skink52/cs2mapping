"""Parented glows (env_particle_glow) -> info_particle_system with a glow that follows its entity.

CS2's env_particle_glow (and the old sprites/glow01 effect) draws where it spawned: moving or re-parenting it does nothing,
and its colortint key is ignored. This converts every parented env_particle_glow (or info_particle_system still carrying a
colortint) to info_particle_system with particles/glowfix/glow_<rrggbb>.vpcf (one per colour, additive sprite, continuous
emitter + position lock, so it follows the entity smoothly) and a generated radial texture.
Each converted glow is named glow_<parent>_<k> so a script can find it. CS2 parenting to a weapon does not follow
the carrier, so weapon-parented glows also need the follow section in <addon>_io.js (see ports/mg_metal_course_level_2).

usage: glowfix.py <vmap in> <vmap out> <addon content root>
"""
import sys, os, re, struct, zlib
import vmapedit
src, dst, out_root = sys.argv[1], sys.argv[2], sys.argv[3]
m = vmapedit.Map(src)
cols = {}
count = {}
for e in m.by_class('env_particle_glow', 'info_particle_system'):
    par = m.P(e, 'parentname', '')
    if not par or not m.P(e, 'colortint', ''): continue
    m.setp(e, 'classname', 'info_particle_system')
    r, g, b = [int(float(x)) for x in m.P(e, 'colortint', '255 255 255').split()[:3]]
    hexc = '%02x%02x%02x' % (r, g, b)
    cols[hexc] = (r, g, b)
    count[par] = count.get(par, 0) + 1
    m.setp(e, 'effect_name', 'particles/glowfix/glow_%s.vpcf' % hexc)
    m.setp(e, 'targetname', 'glow_%s_%d' % (par, count[par]))
    m.setp(e, 'start_active', '1')
    m.delp(e, 's1 env_sprite material')
print(len(cols), 'colours', sum(count.values()), 'glows', count)
print(m.save(dst))

HDR = '<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:vpcf1:version{d47d07e6-072c-49cb-9718-5bfd8d6c3d21} -->\n'
VPCF = HDR + '''{
	_class = "CParticleSystemDefinition"
	m_nMaxParticles = 16
	m_ConstantColor = [ %d, %d, %d, 90 ]
	m_flConstantRadius = 18.0
	m_Renderers =
	[
		{
			_class = "C_OP_RenderSprites"
			m_bAdditive = true
			m_hTexture = resource:"materials/glowfix/glow.vtex"
		},
	]
	m_Emitters =
	[
		{
			_class = "C_OP_ContinuousEmitter"
			m_flEmitRate = 40.0
		},
	]
	m_Initializers =
	[
		{
			_class = "C_INIT_CreateWithinSphere"
			m_fRadiusMin = 0.0
			m_fRadiusMax = 0.0
		},
		{
			_class = "C_INIT_RandomLifeTime"
			m_fLifetimeMin = 0.15
			m_fLifetimeMax = 0.15
		},
	]
	m_Operators =
	[
		{
			_class = "C_OP_Decay"
		},
		{
			_class = "C_OP_PositionLock"
		},
		{
			_class = "C_OP_FadeInSimple"
			m_flFadeInTime = 0.3
		},
		{
			_class = "C_OP_FadeOutSimple"
			m_flFadeOutTime = 0.3
		},
	]
}
'''
pd = out_root + '/particles/glowfix'; os.makedirs(pd, exist_ok=True)
for h, (r, g, b) in cols.items():
    open('%s/glow_%s.vpcf' % (pd, h), 'w', newline='\r\n').write(VPCF % (r, g, b))

N = 64
rows = []
for y in range(N):
    row = bytearray([0])
    for x in range(N):
        d = (((x + .5) / N - .5) ** 2 + ((y + .5) / N - .5) ** 2) ** .5 * 2
        v = max(0.0, 1 - d) ** 2.2
        a = int(v * 255 + .5)
        row += bytes([a, a, a, a])
    rows.append(bytes(row))
raw = b''.join(rows)
def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', N, N, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
md = out_root + '/materials/glowfix'; os.makedirs(md, exist_ok=True)
open(md + '/glow.png', 'wb').write(png)

import radar
v = radar.VTEX.replace('panorama/images/overheadmaps/%(map)s_radar_psd.png', 'materials/glowfix/glow.png').replace('"int" "1024"', '"int" "64"')
open(md + '/glow.vtex', 'w', newline='\r\n').write(v)
