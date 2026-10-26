"""env_laser / env_beam -> func_brush beams (CS2 can't spawn the CS:GO beam entities).

Each beam becomes a never-solid func_brush made of two crossed double-sided quads between its end points, using a
self-illuminated translucent laser material in the beam's colour. Named beams keep their name, so TurnOn / TurnOff /
Toggle inputs become Enable / Disable / Toggle. No damage is added: lasers that did damage in CS:GO are only flagged
when there is no trigger_hurt along them.
"""
import io, os, math
import numpy as np
from PIL import Image
import dmx, vmapedit as V

HERE = os.path.dirname(os.path.abspath(__file__))

LASER_VMAT = '''// Laser beam material (CS2 post-import clean): replaces CS:GO env_laser / env_beam sprites on func_brush beams.

Layer0
{
	shader "csgo_complex.vfx"

	//---- Translucent ----
	F_TRANSLUCENT 1
	g_flOpacityScale "1.000"
	TextureTranslucency "materials/lasers/laser_trans.png"

	//---- Self Illum ----
	F_SELF_ILLUM 1
	g_flSelfIllumScale "4.000"
	g_vSelfIllumTint "[1.000000 1.000000 1.000000 0.000000]"
	TextureSelfIllumMask "materials/lasers/laser_selfillum.png"

	//---- Color ----
	TextureColor "materials/lasers/laser_%(hex)s_color.png"
}
'''

def _profile():
    """across-the-beam profiles (128 rows): translucency and white-core amount"""
    v = np.linspace(-1, 1, 128)
    trans = np.clip(1 - np.abs(v), 0, 1) ** 1.5
    core = np.clip(1 - np.abs(v) * 3, 0, 1) ** 2
    return trans, core

def materials(c, colours):
    trans, core = _profile()
    t = Image.fromarray(np.tile((trans * 255).astype(np.uint8)[:, None], (1, 512)), 'L')
    s = Image.fromarray(np.tile((np.clip(trans * 1.2, 0, 1) * 255).astype(np.uint8)[:, None], (1, 512)), 'L')
    for name, im in (('laser_trans', t), ('laser_selfillum', s)):
        b = io.BytesIO(); im.save(b, 'PNG'); c.write('materials/lasers/%s.png' % name, b.getvalue())
    out = {}
    for col in colours:
        hexs = '%02x%02x%02x' % col
        rgb = np.array(col, np.float32)[None, :] * (1 - core[:, None]) + 255 * core[:, None]
        im = Image.fromarray(np.tile(rgb.astype(np.uint8)[:, None, :], (1, 512, 1)), 'RGB')
        b = io.BytesIO(); im.save(b, 'PNG'); c.write('materials/lasers/laser_%s_color.png' % hexs, b.getvalue())
        c.write('materials/lasers/laser_%s.vmat' % hexs, LASER_VMAT % dict(hex=hexs))
        out[col] = 'materials/lasers/laser_%s.vmat' % hexs
    return out

def build_mesh(m, tm, tnode, a, b, width, mat):
    """crossed double-sided quads from a to b, `width` units wide"""
    memo = {}; nid = [m.next_node_id()]
    j = m.import_subtree(tm, tnode, memo, nid)
    md = m.g(j, b'meshData'); E = m.E
    a = np.array(a, float); b = np.array(b, float); d = b - a; L = float(np.linalg.norm(d)); d /= L
    up = np.array([0, 0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0, 0])
    s1 = np.cross(d, up); s1 /= np.linalg.norm(s1); s2 = np.cross(d, s1); s2 /= np.linalg.norm(s2)
    h = width / 2
    # template vertex layout: quad 1 = 0..3 (start/end x side1), quad 2 = 4..7 (start/end x side2)
    P = [a - s1 * h, b - s1 * h, b + s1 * h, a + s1 * h, a + s2 * h, b + s2 * h, b - s2 * h, a - s2 * h]
    side = [0, 0, 1, 1, 1, 1, 0, 0]; atend = [0, 1, 1, 0, 0, 1, 1, 0]
    g = lambda k: dmx.get(E[md], k)
    for st in dmx.get(E[g(b'vertexData')], b'streams'):
        if E[st]['name'].startswith(b'position'): dmx.geta(E[st], b'data')[2] = [[float(x) for x in p] for p in P]
    evi, efi, evd, fei, eni = g(b'edgeVertexIndices'), g(b'edgeFaceIndices'), g(b'edgeVertexDataIndices'), g(b'faceEdgeIndices'), g(b'edgeNextIndices')
    fnorm = {}
    for f, e0 in enumerate(fei):
        loop = []; e = e0
        for _ in range(8):
            loop.append(P[evi[e]]); e = eni[e]
            if e == e0: break
        n = np.cross(loop[1] - loop[0], loop[2] - loop[0]); fnorm[f] = n / (np.linalg.norm(n) or 1)
    streams = {E[st]['name'].split(b':')[0]: st for st in dmx.get(E[g(b'faceVertexData')], b'streams')}
    tc = dmx.geta(E[streams[b'texcoord']], b'data')[2]; nm = dmx.geta(E[streams[b'normal']], b'data')[2]; tg = dmx.geta(E[streams[b'tangent']], b'data')[2]
    for hh in range(len(evi)):
        v = evi[hh]; k = evd[hh]
        tc[k] = [L / 128.0 if not atend[v] else 0.0, float(side[v])]
        nm[k] = [float(x) for x in fnorm[efi[hh]]]
        tg[k] = [float(-d[0]), float(-d[1]), float(-d[2]), -1.0]
    dmx.set_(E[md], b'materials', dmx.ARR + dmx.T_STR, [mat.encode()])
    return j

def run(m, c):
    beams = m.by_class('env_laser', 'env_beam')
    if not beams: return
    names = {}
    for e in m.entities():
        if m.name(e): names.setdefault(m.name(e).lower(), e)
    targeted = set(dmx.get(cc, b'targetName').decode().lower() for _, cc in m.all_conns())
    segs = []; skipped = []
    for e in beams:
        cls = m.cls(e)
        if cls == 'env_laser':
            t = names.get((m.P(e, 'LaserTarget') or '').lower())
            if t is None: skipped.append(m.name(e) or cls); continue
            a, b = m.origin(e), m.origin(t)
            width = float(m.P(e, 'width', '2') or 2)
        else:
            s = names.get((m.P(e, 'LightningStart') or '').lower()); t = names.get((m.P(e, 'LightningEnd') or '').lower())
            if s is None and t is None: skipped.append(m.name(e) or cls); continue
            a = m.origin(s) if s is not None else m.origin(e); b = m.origin(t) if t is not None else m.origin(e)
            width = float(m.P(e, 'BoltWidth', '2') or 2)
        if np.linalg.norm(np.array(a) - np.array(b)) < 1: skipped.append(m.name(e) or cls); continue
        sf = int(m.P(e, 'spawnflags', '0') or 0)
        start_on = bool(sf & 1) or not m.name(e)                 # CS:GO beams with no name always start on
        col = tuple(int(float(x)) for x in (m.P(e, 'rendercolor', '255 255 255') or '255 255 255').split()[:3])
        segs.append(dict(e=e, a=a, b=b, width=max(2.0, width * 1.5), col=col, on=start_on, name=m.name(e), cls=cls,
                         damage=float(m.P(e, 'damage', '0') or 0)))
    # drop the reverse copy of mutual laser pairs unless I/O targets it
    keep = []
    for s in segs:
        dup = next((k for k in keep if np.allclose(k['a'], s['b'], atol=1) and np.allclose(k['b'], s['a'], atol=1) or
                    np.allclose(k['a'], s['a'], atol=1) and np.allclose(k['b'], s['b'], atol=1)), None)
        if dup and not (s['name'] and s['name'].lower() in targeted and (dup['name'] or '').lower() != s['name'].lower()): continue
        keep.append(s)
    mats = materials(c, sorted(set(s['col'] for s in keep)))
    tm = V.Map(os.path.join(HERE, 'laser_template.vmap')); tnode = tm.children(tm.world)[0]
    hurts = []
    for h in m.by_class('trigger_hurt'):
        bb = m.bounds(h)
        if bb: hurts.append((np.array(bb[0]) - 8, np.array(bb[1]) + 8))
    def hurt_along(a, b):
        for t in np.linspace(0, 1, 9):
            p = np.array(a) * (1 - t) + np.array(b) * t
            if any((p >= lo).all() and (p <= hi).all() for lo, hi in hurts): return True
        return False
    no_hurt = []
    for i, s in enumerate(keep):
        mid = [(x + y) / 2 for x, y in zip(s['a'], s['b'])]
        props = {'targetname': s['name'] or '', 'spawnflags': '2', 'StartDisabled': '0' if s['on'] else '1', 'Solidity': '1',
                 'InputFilter': '0', 'invert_exclusion': '0', 'solidbsp': '0', 'vrad_brush_cast_shadows': '0', 'renderfx': '0', 'rendermode': '0',
                 'renderamt': '255', 'rendercolor': '255 255 255', 'disableshadows': '1', 'disablereceiveshadows': '1', 'fademindist': '-1',
                 'fademaxdist': '0', 'rendertocubemaps': '0', 'lightmapstatic': '0'}
        ent = m.new_entity('func_brush', mid, props)
        j = build_mesh(m, tm, tnode, s['a'], s['b'], s['width'], mats[s['col']])
        dmx.set_(m.E[j], b'disableShadows', dmx.T_INT, 1)
        dmx.geta(m.E[ent], b'children')[2].append(j)
        if s['damage'] > 0 and not hurt_along(s['a'], s['b']): no_hurt.append('%s at %s (damage %g)' % (s['name'] or s['cls'], ' '.join('%g' % x for x in s['a']), s['damage']))
    # inputs
    bnames = set(s['name'].lower() for s in segs if s['name'])
    life = {}
    for s in segs:
        if s['name'] and s['cls'] == 'env_beam': life[s['name'].lower()] = max(life.get(s['name'].lower(), 0), float(m.P(s['e'], 'life', '0') or 0))
    n_in = 0; n_strike = 0
    for e, cc in list(m.all_conns()):
        t = dmx.get(cc, b'targetName').decode().lower(); i = dmx.get(cc, b'inputName').decode().lower()
        if t in bnames and i in ('turnon', 'turnoff', 'toggle'):
            dmx.set_(cc, b'inputName', dmx.T_STR, {'turnon': b'Enable', 'turnoff': b'Disable', 'toggle': b'Toggle'}[i]); n_in += 1
        elif t in bnames and i == 'strikeonce':      # one strike lasting the beam's life: Enable now, Disable after life
            dmx.set_(cc, b'inputName', dmx.T_STR, b'Enable'); n_strike += 1
            if life.get(t, 0) > 0:
                o, tg, _, prm, dl, tf = m.conn_tuple(cc)
                m.add_conn(e, o, tg, 'Disable', '', dl + life[t], tf)
    for e in beams: m.remove_node(e)
    nl = sum(1 for s in segs if s['cls'] == 'env_laser'); nb = len(segs) - nl
    c.log.append('%d env_laser + %d env_beam (CS2 cannot spawn them) -> %d never-solid func_brush beams between their end points (mutual laser pairs drawn once), coloured self-illuminated laser materials materials/lasers/laser_<rgb>.vmat; %d TurnOn/TurnOff/Toggle -> Enable/Disable/Toggle; %d StrikeOnce -> Enable, then Disable after the beam life; no damage added'
                 % (nl, nb, len(keep), n_in, n_strike))
    if no_hurt: c.todo.append('these lasers did damage in CS:GO but there is no trigger_hurt along them, so in CS2 they are only visual: %s' % ', '.join(sorted(set(no_hurt))))
    if skipped: c.todo.append('beams with no usable end point, removed: %s' % ', '.join(skipped))
