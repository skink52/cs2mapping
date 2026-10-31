"""point_spotlight beams (Valve's importer leaves point_spotlight out: the CS:GO spotlight cone sprite is gone in CS2).

Each point_spotlight from the CS:GO entity list becomes a never-solid func_brush: crossed double-sided quads from the spotlight along its
forward axis, widening from SPOT_START x width to the full spotlightwidth, cut short where the beam meets world geometry, with an
additive csgo_unlitgeneric material (materials/spotlights/spot_<rgb>.vmat) that fades out along the beam and towards its edges; strength
from renderamt (CS:GO default 255, these maps often 50). Named spotlights keep their name; LightOn/LightOff -> Enable/Disable.
The light itself is the separate light_spot the mapper placed, which the importer keeps as light_barn.

    spotbeam.run(m, c, spots)   spots = [dict of CS:GO keyvalues] (from a VMF or the BSP entity lump)
From ba_jail_keimusho (31 Oct 2026)."""
import io, os, math
import numpy as np
from PIL import Image
import dmx, vmapedit as V, beams, lighting

HERE = os.path.dirname(os.path.abspath(__file__))
SPOT_START = 0.25

SPOT_VMAT = '''// point_spotlight beam (CS2 post-import clean)
Layer0
{
	shader "csgo_unlitgeneric.vfx"
	F_BLEND_MODE 4
	F_RENDER_BACKFACES 1
	TextureColor "materials/spotlights/spot_%(hex)s_color.png"
	g_vColorTint "[1.000000 1.000000 1.000000 0.000000]"
}
'''

def _texture(col, strength):
    u = np.linspace(0, 1, 256)[None, :]                     # along the beam (0 = lamp)
    v = np.linspace(-1, 1, 64)[:, None]                     # across
    a = (1 - u) ** 1.6 * np.clip(1 - np.abs(v), 0, 1) ** 1.4 * strength
    rgb = (np.array(col, np.float32)[None, None, :] * a[:, :, None]).clip(0, 255).astype(np.uint8)
    b = io.BytesIO(); Image.fromarray(rgb, 'RGB').save(b, 'PNG'); return b.getvalue()

def _forward(ang):
    p, y = math.radians(ang[0]), math.radians(ang[1])
    return np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p)])

def run(m, c, spots):
    if not spots: return
    polys = lighting.world_polys(m)
    solid, lo = lighting.voxelise(polys, 8.0) if polys else (None, None)
    def hit_dist(a, d, L):
        if solid is None: return L
        S = np.array(solid.shape)
        for t in np.arange(8.0, L, 4.0):
            i = np.floor((a + d * t - lo) / 8.0).astype(int)
            if (i < 0).any() or (i >= S).any(): return L
            if solid[tuple(i)] == 1: return max(16.0, t - 4)
        return L
    tm = V.Map(os.path.join(HERE, 'laser_template.vmap')); tnode = tm.children(tm.world)[0]
    mats = {}; n = 0
    for s in spots:
        a = np.array([float(x) for x in s.get('origin', '0 0 0').split()[:3]])
        ang = [float(x) for x in (s.get('angles') or '0 0 0').split()[:3]]
        d = _forward(ang)
        L = hit_dist(a, d, float(s.get('spotlightlength', '500') or 500))
        w = float(s.get('spotlightwidth', '50') or 50)
        col = tuple(int(float(x)) for x in (s.get('rendercolor') or '255 255 255').split()[:3])
        strength = min(1.0, float(s.get('renderamt', '255') or 255) / 255.0 * 1.2)
        key = (col, round(strength, 2))
        if key not in mats:
            hexs = '%02x%02x%02x_%02d' % (col + (int(strength * 99),))
            c.write('materials/spotlights/spot_%s_color.png' % hexs, _texture(col, strength))
            c.write('materials/spotlights/spot_%s.vmat' % hexs, SPOT_VMAT % dict(hex=hexs))
            mats[key] = 'materials/spotlights/spot_%s.vmat' % hexs
        b = a + d * L
        name = s.get('targetname') or ''
        sf = int(float(s.get('spawnflags', '0') or 0))
        props = {'targetname': name, 'spawnflags': '2', 'StartDisabled': '0' if (sf & 1 or not name) else '1', 'Solidity': '1',
                 'InputFilter': '0', 'invert_exclusion': '0', 'solidbsp': '0', 'vrad_brush_cast_shadows': '0', 'renderfx': '0', 'rendermode': '0',
                 'renderamt': '255', 'rendercolor': '255 255 255', 'disableshadows': '1', 'disablereceiveshadows': '1', 'fademindist': '-1',
                 'fademaxdist': '0', 'rendertocubemaps': '0', 'lightmapstatic': '0'}
        ent = m.new_entity('func_brush', ((a + b) / 2).tolist(), props)
        j = beams.build_mesh(m, tm, tnode, a.tolist(), b.tolist(), w, mats[key])
        # taper: start vertices pulled in to SPOT_START of the width; texcoords 0 (lamp) .. 1 (end)
        md = m.g(j, b'meshData'); E = m.E; g = lambda k: dmx.get(E[md], k)
        for st in dmx.get(E[g(b'vertexData')], b'streams'):
            if E[st]['name'].startswith(b'position'):
                P = dmx.geta(E[st], b'data')[2]
                for k in (0, 3, 4, 7):
                    p = np.array(P[k]); P[k] = [float(x) for x in a + (p - a) * SPOT_START]
        evi, evd = g(b'edgeVertexIndices'), g(b'edgeVertexDataIndices')
        streams = {E[st]['name'].split(b':')[0]: st for st in dmx.get(E[g(b'faceVertexData')], b'streams')}
        tc = dmx.geta(E[streams[b'texcoord']], b'data')[2]
        atend = [0, 1, 1, 0, 0, 1, 1, 0]; side = [0, 0, 1, 1, 1, 1, 0, 0]
        for hh in range(len(evi)):
            tc[evd[hh]] = [float(atend[evi[hh]]) * 0.999 + 0.0005, float(side[evi[hh]])]
        dmx.set_(m.E[j], b'disableShadows', dmx.T_INT, 1)
        dmx.geta(m.E[ent], b'children')[2].append(j)
        n += 1
    names = set((s.get('targetname') or '').lower() for s in spots) - {''}
    ni = 0
    for e, cc in m.all_conns():
        t = dmx.get(cc, b'targetName').decode().lower(); i = dmx.get(cc, b'inputName').decode().lower()
        if t in names and i in ('lighton', 'lightoff'):
            dmx.set_(cc, b'inputName', dmx.T_STR, b'Enable' if i == 'lighton' else b'Disable'); ni += 1
    c.log.append('point_spotlight: %d beams rebuilt as never-solid func_brush cones (additive, fading, cut at the first wall/floor; materials/spotlights/); %d LightOn/LightOff -> Enable/Disable' % (n, ni))
