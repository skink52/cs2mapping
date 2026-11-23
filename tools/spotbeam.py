"""point_spotlight beams (Valve's importer leaves point_spotlight out: the CS:GO spotlight cone sprite is gone in CS2).

Each point_spotlight from the CS:GO entity list becomes a never-solid func_brush: crossed double-sided quads from the spotlight along its
forward axis, widening from SPOT_START x width to the full spotlightwidth, cut short where the beam meets world geometry, with an
additive csgo_unlitgeneric material (materials/spotlights/spot_<rgb>.vmat) that fades out along the beam and towards its edges; strength
from renderamt (CS:GO default 255, these maps often 50). Named spotlights keep their name; LightOn/LightOff -> Enable/Disable.
The light itself is the separate light_spot the mapper placed, which the importer keeps as light_barn.

    spotbeam.run(m, c, spots)   spots = [dict of CS:GO keyvalues] (from a VMF or the BSP entity lump)
    spotbeam.from_vmf(path)     point_spotlight + beam_spotlight dicts from a VMF (keys lower case)
    python spotbeam.py <map.vmap> <map.vmf | -> <out.vmap>   (- : only the beam_spotlights the importer kept in the vmap)
From ba_jail_keimusho (31 Oct 2026).

beam_spotlight (CS:GO only; Valve's importer keeps it but CS2 draws nothing): the same cone along its forward axis, the kept entity removed.
Width = spotlightwidth, strength renderamt x HDRColorScale. With rotation (spawnflags 4 = start rotating, or Start / Stop / Reverse sent
to it) a func_rotating `<name>_rot` at the spotlight (its angles, maxspeed, flags 8 reverse -> 2, 16 X axis -> 4, 32 Y axis -> 8, never solid,
a tiny toolsinvisible mesh) turns the beam: the beam func_brush stays unparented in the map and gets SetParent from port_logic_auto on
OnMapSpawn / OnMultiNewRound (a func_brush parented in the map never shows: cs2-gotchas, doorsolid.attach). Start / Stop / Reverse go to
`<name>_rot`; LightOn / LightOff -> Enable / Disable on the beam. Unnamed rotating ones are named port_bspot_<n>. The dynamic light a
beam_spotlight casts (no spawnflags 2) is not rebuilt; they are counted in TO CHECK."""
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

KEYS = ('origin', 'angles', 'targetname', 'spotlightlength', 'spotlightwidth', 'rendercolor', 'renderamt', 'hdrcolorscale', 'maxspeed',
        'spawnflags')


def _k(s, k, d=None):
    v = s.get(k)
    if v is None: v = next((x for kk, x in s.items() if kk.lower() == k), None)
    return d if v in (None, '') else v


def from_vmf(path, classes=('point_spotlight', 'beam_spotlight')):
    import vmf as vmfmod
    with open(path, encoding='utf-8', errors='replace') as fh: root = vmfmod.parse(fh.read())
    return [{k.lower(): v for k, v in e.kv} for e in root.ch if e.name == 'entity' and (e.get('classname') or '').lower() in classes]


def kept(m):
    """beam_spotlight entities the importer kept in the vmap, as CS:GO keyvalue dicts (origin / angles from the node)"""
    out = []
    for e in m.by_class('beam_spotlight'):
        d = {'classname': 'beam_spotlight', 'origin': ' '.join('%g' % x for x in m.origin(e)),
             'angles': ' '.join('%g' % x for x in (m.g(e, b'angles') or [0, 0, 0]))}
        for k in KEYS[2:]:
            v = m.P(e, k)
            if v in (None, '') and k == 'hdrcolorscale': v = m.P(e, 'HDRColorScale')
            if v not in (None, ''): d[k] = v
        out.append(d)
    return out


ROT_FLAGS = ((8, 2), (16, 4), (32, 8))   # beam_spotlight reverse / X axis / Y axis -> func_rotating


def _rot_flags(sf):
    f = 64 | (1 if sf & 4 else 0)        # 64: never solid; 1: start on
    for a, b in ROT_FLAGS:
        if sf & a: f |= b
    return f


def run(m, c, spots):
    if not spots: return
    spots = [s for s in spots if _k(s, 'classname', 'point_spotlight').lower() in ('point_spotlight', 'beam_spotlight')]
    rot_in = {}                                   # lower name -> inputs sent to it
    for e, cc in m.all_conns():
        rot_in.setdefault(dmx.get(cc, b'targetName').decode().lower(), set()).add(dmx.get(cc, b'inputName').decode().lower())
    done_mid = set(tuple(int(round(x)) for x in m.origin(e)) for e in m.by_class('func_brush'))
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
    mats = {}; n = 0; nb = 0; nrot = 0; dyn = 0; rot_names = {}; attach = []
    for s in spots:
        bs = _k(s, 'classname', 'point_spotlight').lower() == 'beam_spotlight'
        a = np.array([float(x) for x in _k(s, 'origin', '0 0 0').split()[:3]])
        ang = [float(x) for x in _k(s, 'angles', '0 0 0').split()[:3]]
        d = _forward(ang)
        L = hit_dist(a, d, float(_k(s, 'spotlightlength', '500')))
        if tuple(int(round(x)) for x in (a + d * L / 2)) in done_mid: continue     # already rebuilt (rerun)
        if bs:
            for e in [e for e in m.by_class('beam_spotlight') if np.linalg.norm(np.array(m.origin(e), float) - a) < 1.0]:
                m.remove_node(e)                                             # the importer's copy draws nothing
        w = float(_k(s, 'spotlightwidth', '50'))
        col = tuple(int(float(x)) for x in _k(s, 'rendercolor', '255 255 255').split()[:3])
        scale = min(1.0, float(_k(s, 'hdrcolorscale', '1'))) if bs else 1.0
        strength = min(1.0, float(_k(s, 'renderamt', '255')) / 255.0 * 1.2 * scale)
        key = (col, round(strength, 2))
        if key not in mats:
            hexs = '%02x%02x%02x_%02d' % (col + (int(strength * 99),))
            c.write('materials/spotlights/spot_%s_color.png' % hexs, _texture(col, strength))
            c.write('materials/spotlights/spot_%s.vmat' % hexs, SPOT_VMAT % dict(hex=hexs))
            mats[key] = 'materials/spotlights/spot_%s.vmat' % hexs
        b = a + d * L
        name = _k(s, 'targetname', '')
        sf = int(float(_k(s, 'spawnflags', '0')))
        rot = bs and bool(sf & 4 or rot_in.get(name.lower(), set()) & {'start', 'stop', 'reverse', 'toggle'})
        if rot and not name: nrot += 1; name = 'port_bspot_%d' % nrot
        if bs and not sf & 2: dyn += 1
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
        if rot:
            rn = name + '_rot'
            r = m.new_entity('func_rotating', a.tolist(), {'targetname': rn, 'spawnflags': str(_rot_flags(sf)), 'maxspeed': _k(s, 'maxspeed', '100'),
                                                           'fanfriction': '20', 'solidbsp': '0', 'renderamt': '255', 'rendercolor': '255 255 255',
                                                           'disableshadows': '1'}, angles=ang)
            jr = beams.build_mesh(m, tm, tnode, a.tolist(), (a + d * 2).tolist(), 1.0, 'materials/tools/toolsinvisible.vmat')
            dmx.geta(m.E[r], b'children')[2].append(jr)
            rot_names[name.lower()] = rn; attach.append((name, rn))
        if bs: nb += 1
        else: n += 1
    if attach:
        la = [e for e in m.by_class('logic_auto') if m.name(e) == 'port_logic_auto']
        la = la[0] if la else m.new_entity('logic_auto', [float(x) for x in m.origin(m.entities()[0])], {'targetname': 'port_logic_auto', 'spawnflags': '0'})
        have_c = {tuple(m.conn_tuple(cn)[:3]) for cn in m.conns(la)}
        for bn, rn in attach:
            for out in ('OnMapSpawn', 'OnMultiNewRound'):
                if (out, bn, 'SetParent') not in have_c: m.add_conn(la, out, bn, 'SetParent', rn, 0.0)
    names = set(_k(s, 'targetname', '').lower() for s in spots) - {''}
    ni = nr = 0
    for e, cc in m.all_conns():
        t = dmx.get(cc, b'targetName').decode().lower(); i = dmx.get(cc, b'inputName').decode().lower()
        if t in names and i in ('lighton', 'lightoff'):
            dmx.set_(cc, b'inputName', dmx.T_STR, b'Enable' if i == 'lighton' else b'Disable'); ni += 1
        elif t in rot_names and i in ('start', 'stop', 'reverse', 'toggle'):
            dmx.set_(cc, b'targetName', dmx.T_STR, rot_names[t].encode()); nr += 1
    if n or not nb:
        c.log.append('point_spotlight: %d beams rebuilt as never-solid func_brush cones (additive, fading, cut at the first wall/floor; materials/spotlights/); %d LightOn/LightOff -> Enable/Disable' % (n, ni))
    if nb:
        c.log.append("beam_spotlight: %d beams rebuilt as func_brush cones (the importer's entities removed), %d turned by a func_rotating <name>_rot "
                     '(SetParent from port_logic_auto), %d Start/Stop/Reverse retargeted to it' % (nb, len(attach), nr))
        if dyn: c.todo.append('beam_spotlight: %d cast a dynamic light in CS:GO (no spawnflags 2); only the beam is rebuilt - add a light_barn where the light matters' % dyn)
        if attach: c.todo.append('beam_spotlight: check in game that the rotating beams turn about the lamp: %s' % ', '.join(b for b, _ in attach)[:400])


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='point_spotlight / beam_spotlight -> func_brush beam cones')
    ap.add_argument('vmap'); ap.add_argument('vmf', help='the decompiled VMF, or - for the beam_spotlights the importer kept'); ap.add_argument('out')
    ap.add_argument('--files', help='folder to write the generated materials into (content-relative paths); default: not written')
    a = ap.parse_args(argv)
    m = V.Map(a.vmap)
    spots = kept(m) if a.vmf == '-' else from_vmf(a.vmf)
    class C: pass
    c = C(); c.log = []; c.todo = []; c.files = {}
    c.write = lambda rel, data: c.files.__setitem__(rel, data if isinstance(data, bytes) else data.encode('utf-8'))
    run(m, c, spots)
    for l in c.log: print(l)
    for l in c.todo: print('TO CHECK:', l)
    if a.files:
        for rel, data in c.files.items():
            q = os.path.join(a.files, rel); os.makedirs(os.path.dirname(q), exist_ok=True)
            with open(q, 'wb') as fh: fh.write(data)
    print('%d files%s: %s' % (len(c.files), (' written under ' + a.files) if a.files else ' (not written; give --files)', ', '.join(sorted(c.files))[:300]))
    m.prune(); print('wrote', a.out, m.save(a.out), 'bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
