"""Aircraft effect models (prop_dynamic, non-solid): falling bomb, gun tracer streak, bomb-sight ground ring, gun-sight pip.
Model forward is +x (scripts orient them by yaw/pitch). Usage: fx_models.py <addon>"""
import os, sys, math
import numpy as np
from PIL import Image
import geo, modelio

OUT = sys.argv[1]
REL_M = 'models/tw/fx'; REL_T = 'materials/models/tw/fx'
os.makedirs(os.path.join(OUT, REL_M), exist_ok=True); os.makedirs(os.path.join(OUT, REL_T), exist_ok=True)


def emissive(name, rgb, bright):
    Image.new('RGB', (4, 4), rgb).save(os.path.join(OUT, REL_T, name + '_color.png'))
    Image.new('L', (4, 4), 255).save(os.path.join(OUT, REL_T, 'fx_mask.png'))
    open(os.path.join(OUT, REL_T, name + '.vmat'), 'w', newline='\n').write(f"""// mg_trenchwarfare effect material
Layer0
{{
	shader "csgo_vertexlitgeneric.vfx"
	F_SELF_ILLUM 1
	TextureColor "{REL_T}/{name}_color.png"
	TextureSelfIllumMask "{REL_T}/fx_mask.png"
	g_flSelfIllumBrightness "{bright:.3f}"
	g_flSelfIllumScale "1.000"
	g_flSelfIllumAlbedoFactor "1.000"
	g_vSelfIllumTint "[1.000000 1.000000 1.000000 0.000000]"
	TextureNormal "materials/default/default_normal.tga"
	TextureRoughness "materials/default/default_rough.tga"
}}
""")
    return f'{REL_T}/{name}.vmat'


def ring(r0, r1, n=48, z=0.0, axis='z', double=True):
    m = geo.Mesh()
    th = np.linspace(0, 2 * np.pi, n + 1)
    V = []; F = []
    for k in range(n):
        a, b = th[k], th[k + 1]
        q = [(r0 * math.cos(a), r0 * math.sin(a)), (r1 * math.cos(a), r1 * math.sin(a)), (r1 * math.cos(b), r1 * math.sin(b)), (r0 * math.cos(b), r0 * math.sin(b))]
        i0 = len(V); V += q; F += [(i0, i0 + 1, i0 + 2), (i0, i0 + 2, i0 + 3)]
    return quads(V, F, z, axis, double)


def quads(V2, F, z, axis, double=True):
    V = np.array([(x, y, z) for x, y in V2], float)
    if axis == 'x': V = V[:, [2, 0, 1]]                     # ring in the YZ plane, facing +x
    F = np.array(F, np.int64)
    if double: V = np.concatenate([V, V]); F = np.concatenate([F, F[:, ::-1] + len(V2)])     # double-sided
    m = geo.Mesh(); m.V = V; m.N = np.tile([0, 0, 1.0] if axis == 'z' else [1.0, 0, 0], (len(V), 1)); m.F = F
    return m


def bar(x0, y0, x1, y1, z=0.0, axis='z', double=True):
    return quads([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], [(0, 1, 2), (0, 2, 3)], z, axis, double)


def merge(ms):
    out = geo.Mesh(); V = []; N = []; F = []; o = 0
    for m in ms:
        V.append(m.V); N.append(m.N); F.append(m.F + o); o += len(m.V)
    out.V = np.concatenate(V); out.N = np.concatenate(N); out.F = np.concatenate(F)
    return out


def write(name, mesh, mat_vmat, uv=None):
    d = os.path.join(OUT, REL_M, name); os.makedirs(d, exist_ok=True)
    if uv is None: uv = np.zeros((len(mesh.V), 2))
    modelio.write_smd(os.path.join(d, name + '.smd'), mesh, uv, name + '.vmat')
    open(os.path.join(d, name + '.vmdl'), 'w', newline='\n').write(
        modelio.vmdl_text(name, f'{REL_M}/{name}', [name], [(name + '.vmat', mat_vmat)], [], archetype='', entity='prop_dynamic'))


# bomb: 46 long, nose at +x, four tail fins
prof = [(0.01, -24), (3.2, -22), (3.4, -12), (5.6, -6), (6.0, 6), (5.4, 14), (3.6, 20), (1.2, 23), (0.01, 23.5)]
body = geo.lathe(prof, sides=14, mat='m')
body.V = np.stack([body.V[:, 2], body.V[:, 1], -body.V[:, 0]], 1); body.N = np.stack([body.N[:, 2], body.N[:, 1], -body.N[:, 0]], 1)
fins = []
for k in range(4):
    a = k * math.pi / 2
    f = geo.rbox(9, 0.6, 6, r=0.2, mat='m'); R = geo.rot('x', math.degrees(a))
    f.V = (f.V + np.array([-19, 0, 5.5])) @ R.T; f.N = f.N @ R.T
    fins.append(f)
bomb = merge([body] + fins)
write('tw_bomb', bomb, 'materials/de_overpass/metal/rusty_metal_1.vmat', uv=bomb.V[:, [0, 2]] / 48.0)
# tracer: a glowing streak behind its head (origin = head)
tr = geo.tube([(-110, 0, 0), (0, 0, 0)], [0.5, 1.4], sides=6, mat='m')
write('tw_tracer', tr, emissive('fx_tracer', (255, 196, 90), 40.0))
# bomb sight: ring with ticks, ONE-SIDED facing +z: the script holds it between the pilot's camera and the landing point, facing the
# camera, a few hundred units up - players on the ground below see its back face, which isn't drawn
bs = merge([ring(108, 118, double=False), ring(14, 20, double=False)] +
           [bar(*b, double=False) for b in ((126, -3, 168, 3), (-168, -3, -126, 3), (-3, 126, 3, 168), (-3, -168, 3, -126))])
write('tw_bombsight', bs, emissive('fx_bombsight', (255, 70, 40), 12.0))
# gun sight: ring + cross facing +x (towards a camera behind the plane)
gs = merge([ring(34, 38, axis='x'), ring(0.0, 4, n=12, axis='x')] +
           [bar(*b, axis='x') for b in ((44, -1.5, 66, 1.5), (-66, -1.5, -44, 1.5), (-1.5, 44, 1.5, 66), (-1.5, -66, 1.5, -44))])
write('tw_gunsight', gs, emissive('fx_gunsight', (255, 220, 120), 12.0))
print('fx models ->', os.path.join(OUT, REL_M))
