"""Self-lit effect models for scripts (prop_dynamic, non-solid, forward = +x so a script can orient them by yaw/pitch):
a glowing tracer streak (origin at its head), a ground ring marker with ticks (aim point, landing spot), a ring-and-cross sight
facing +x (a gunsight pip for a camera behind it), and a finned bomb as an example of a plain shaded model.
Glow comes from a csgo_vertexlitgeneric + F_SELF_ILLUM material (emissive_vmat); every quad is double-sided.

usage: fx_models.py <addon content dir> [--prefix fx] [--only tracer,marker,sight,bomb]
Writes models/<CS2_MODEL_PREFIX>/<prefix>/<name>/<name>.{smd,vmdl} and materials/models/<CS2_MODEL_PREFIX>/<prefix>/*.vmat/png.
Python: fx_models.emissive(out, rel, 'fx_red', (255, 60, 40), 12.0) for your own glowing materials, ring()/bar()/merge() for shapes.

From trenchwarfare-cs2/tools/fx_models.py (MIT), made project-neutral.
"""
import os, sys, math, argparse
import numpy as np
from PIL import Image
import geo, modelio

PREFIX = os.environ.get('CS2_MODEL_PREFIX', 'props')
BOMB_MAT = 'materials/de_overpass/metal/rusty_metal_1.vmat'      # stock material for the plain example


def emissive(out, rel_t, name, rgb, bright):
    """self-lit material: flat colour, full self-illum mask; brightness 12 for markers, ~40 for a tracer seen in daylight"""
    d = os.path.join(out, rel_t); os.makedirs(d, exist_ok=True)
    Image.new('RGB', (4, 4), tuple(rgb)).save(os.path.join(d, name + '_color.png'))
    Image.new('L', (4, 4), 255).save(os.path.join(d, 'fx_mask.png'))
    open(os.path.join(d, name + '.vmat'), 'w', newline='\n').write(f"""// self-lit effect material (AI-generated)
Layer0
{{
	shader "csgo_vertexlitgeneric.vfx"
	F_SELF_ILLUM 1
	TextureColor "{rel_t}/{name}_color.png"
	TextureSelfIllumMask "{rel_t}/fx_mask.png"
	g_flSelfIllumBrightness "{bright:.3f}"
	g_flSelfIllumScale "1.000"
	g_flSelfIllumAlbedoFactor "1.000"
	g_vSelfIllumTint "[1.000000 1.000000 1.000000 0.000000]"
	TextureNormal "materials/default/default_normal.tga"
	TextureRoughness "materials/default/default_rough.tga"
}}
""")
    return f'{rel_t}/{name}.vmat'


def quads(V2, F, z, axis):
    """flat 2D shape -> double-sided mesh, in the XY plane (axis='z') or the YZ plane facing +x (axis='x')"""
    V = np.array([(x, y, z) for x, y in V2], float)
    if axis == 'x': V = V[:, [2, 0, 1]]
    F = np.array(F, np.int64)
    V = np.concatenate([V, V]); F = np.concatenate([F, F[:, ::-1] + len(V2)])
    m = geo.Mesh(); m.V = V; m.N = np.tile([0, 0, 1.0] if axis == 'z' else [1.0, 0, 0], (len(V), 1)); m.F = F
    return m


def ring(r0, r1, n=48, z=0.0, axis='z'):
    th = np.linspace(0, 2 * np.pi, n + 1); V = []; F = []
    for k in range(n):
        a, b = th[k], th[k + 1]
        i0 = len(V)
        V += [(r0 * math.cos(a), r0 * math.sin(a)), (r1 * math.cos(a), r1 * math.sin(a)), (r1 * math.cos(b), r1 * math.sin(b)), (r0 * math.cos(b), r0 * math.sin(b))]
        F += [(i0, i0 + 1, i0 + 2), (i0, i0 + 2, i0 + 3)]
    return quads(V, F, z, axis)


def bar(x0, y0, x1, y1, z=0.0, axis='z'):
    return quads([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], [(0, 1, 2), (0, 2, 3)], z, axis)


def merge(ms):
    out = geo.Mesh()
    o = np.cumsum([0] + [len(m.V) for m in ms[:-1]])
    out.V = np.concatenate([m.V for m in ms]); out.N = np.concatenate([m.N for m in ms]); out.F = np.concatenate([m.F + k for m, k in zip(ms, o)])
    return out


def write(out, rel_m, name, mesh, mat_vmat, uv=None):
    d = os.path.join(out, rel_m, name); os.makedirs(d, exist_ok=True)
    if uv is None: uv = np.zeros((len(mesh.V), 2))
    modelio.write_smd(os.path.join(d, name + '.smd'), mesh, uv, name + '.vmat')
    open(os.path.join(d, name + '.vmdl'), 'w', newline='\n').write(
        modelio.vmdl_text(name, f'{rel_m}/{name}', [name], [(name + '.vmat', mat_vmat)], [], archetype='', entity='prop_dynamic', single_lod=True))
    return f'{rel_m}/{name}/{name}.vmdl'


def build(out, prefix='fx', only=None):
    rel_m = 'models/%s/%s' % (PREFIX, prefix); rel_t = 'materials/models/%s/%s' % (PREFIX, prefix)
    made = {}
    want = lambda k: only is None or k in only
    if want('tracer'):        # glowing streak behind its head; fly it at a few thousand u/s, every Nth round
        tr = geo.tube([(-110, 0, 0), (0, 0, 0)], [0.5, 1.4], sides=6, mat='m')
        made['tracer'] = write(out, rel_m, 'fx_tracer', tr, emissive(out, rel_t, 'fx_tracer', (255, 196, 90), 40.0))
    if want('marker'):        # ground ring with four ticks, lies flat
        mk = merge([ring(108, 118), ring(14, 20)] + [bar(*b) for b in ((126, -3, 168, 3), (-168, -3, -126, 3), (-3, 126, 3, 168), (-3, -168, 3, -126))])
        made['marker'] = write(out, rel_m, 'fx_marker', mk, emissive(out, rel_t, 'fx_marker', (255, 70, 40), 12.0))
    if want('sight'):         # ring + cross facing +x
        gs = merge([ring(34, 38, axis='x'), ring(0.0, 4, n=12, axis='x')] +
                   [bar(*b, axis='x') for b in ((44, -1.5, 66, 1.5), (-66, -1.5, -44, 1.5), (-1.5, 44, 1.5, 66), (-1.5, -66, 1.5, -44))])
        made['sight'] = write(out, rel_m, 'fx_sight', gs, emissive(out, rel_t, 'fx_sight', (255, 220, 120), 12.0))
    if want('bomb'):          # 46 long, nose at +x, four tail fins, stock metal
        prof = [(0.01, -24), (3.2, -22), (3.4, -12), (5.6, -6), (6.0, 6), (5.4, 14), (3.6, 20), (1.2, 23), (0.01, 23.5)]
        body = geo.lathe(prof, sides=14, mat='m')
        body.V = np.stack([body.V[:, 2], body.V[:, 1], -body.V[:, 0]], 1); body.N = np.stack([body.N[:, 2], body.N[:, 1], -body.N[:, 0]], 1)
        fins = []
        for k in range(4):
            f = geo.rbox(9, 0.6, 6, r=0.2, mat='m'); R = geo.rot('x', 90.0 * k)
            f.V = (f.V + np.array([-19, 0, 5.5])) @ R.T; f.N = f.N @ R.T
            fins.append(f)
        bomb = merge([body] + fins)
        made['bomb'] = write(out, rel_m, 'fx_bomb', bomb, BOMB_MAT, uv=bomb.V[:, [0, 2]] / 48.0)
    for k, v in made.items(): print('%-7s %s' % (k, v))
    return made


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='self-lit effect models')
    ap.add_argument('out'); ap.add_argument('--prefix', default='fx'); ap.add_argument('--only')
    a = ap.parse_args()
    build(a.out, a.prefix, set(a.only.split(',')) if a.only else None)
