"""Small helpers shared by the generators: Source 2 model (SMD + vmdl) and material (vmat + png) writers."""
import os
import numpy as np
from PIL import Image

VMDL_HEAD = """<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc41:version{12fc9d44-453a-4ae4-b4d9-7e2ac0bbd4e0} -->
{
	rootNode =
	{
		_class = "RootNode"
		children =
		[
			{
				_class = "MaterialGroupList"
				children =
				[
%s
				]
			},
			{
				_class = "RenderMeshList"
				children =
				[
					{
						_class = "RenderMeshFile"
						name = "%s"
						filename = "%s"
						import_scale = 1.0
						import_filter =
						{
							exclude_by_default = false
							exception_list = [  ]
						}
					},
				]
			},
		]
		model_archetype = ""
		primary_associated_entity = ""
		document_sub_type = "ModelDocSubType_None"
	}
}
"""


def _group(cls, name, remaps):
    rm = "\n".join('\t\t\t\t\t\t\t{\n\t\t\t\t\t\t\t\tfrom = "%s"\n\t\t\t\t\t\t\t\tto = "%s"\n\t\t\t\t\t\t\t},' % r for r in remaps)
    if cls == 'DefaultMaterialGroup':
        return ('\t\t\t\t\t{\n\t\t\t\t\t\t_class = "DefaultMaterialGroup"\n\t\t\t\t\t\tremaps =\n\t\t\t\t\t\t[\n%s\n\t\t\t\t\t\t]\n'
                '\t\t\t\t\t\tuse_global_default = false\n\t\t\t\t\t\tglobal_default_material = ""\n\t\t\t\t\t},' % rm)
    return '\t\t\t\t\t{\n\t\t\t\t\t\t_class = "MaterialGroup"\n\t\t\t\t\t\tname = "%s"\n\t\t\t\t\t\tremaps =\n\t\t\t\t\t\t[\n%s\n\t\t\t\t\t\t]\n\t\t\t\t\t},' % (name, rm)


def smd_text(tris):
    """tris: list of (smd_material_name, [(x,y,z,u,v)]*3, (nx,ny,nz)) in game coordinates (x east, y north, z up)."""
    out = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0",
           "0 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000", "end", "triangles"]
    for mat, verts, n in tris:
        out.append(mat)
        for (x, y, z, u, v) in verts:
            # ModelDoc turns SMD imports 90 degrees: write (y, -x, z) to cancel it (same fix as FreeDM)
            out.append("0 %.3f %.3f %.3f %.4f %.4f %.4f %.5f %.5f" % (y, -x, z, n[1], -n[0], n[2], u, v))
    out.append("end")
    return "\n".join(out) + "\n"


def write_model(out_dir, rel_dir, name, tris, default_mats, skins=None):
    """rel_dir like 'models/spr/cars'; default_mats: {smd material name: 'materials/x.vmat'}; skins: [(name, [(from_vmat, to_vmat)])]"""
    d = os.path.join(out_dir, rel_dir)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, name + '.smd'), 'w', newline='\n').write(smd_text(tris))
    groups = [_group('DefaultMaterialGroup', None, [(k + '.vmat', v) for k, v in default_mats.items()])]
    for sname, remaps in (skins or []):
        groups.append(_group('MaterialGroup', sname, remaps))
    open(os.path.join(d, name + '.vmdl'), 'w', newline='\n').write(VMDL_HEAD % ("\n".join(groups), name, '%s/%s.smd' % (rel_dir, name)))
    return '%s/%s.vmdl' % (rel_dir, name)


def write_material(out_dir, rel_path, color_png, alpha_png=None, blend=0, backfaces=False, tint=(1, 1, 1), comment='', extra=()):
    """rel_path like 'materials/spr/road_a' (no extension). blend: 0 opaque, 1 translucent, 2 alpha test."""
    d = os.path.join(out_dir, os.path.dirname(rel_path))
    os.makedirs(d, exist_ok=True)
    base = os.path.basename(rel_path)
    Image.fromarray(np.ascontiguousarray(color_png[..., :3])).save(os.path.join(d, base + '_color.png'))
    lines = ['// %s' % comment, 'Layer0', '{', '\tshader "csgo_unlitgeneric.vfx"', '\tF_BLEND_MODE %d' % blend]
    if backfaces: lines.append('\tF_RENDER_BACKFACES 1')
    lines.append('\tTextureColor "%s_color.png"' % rel_path)
    if alpha_png is not None:
        Image.fromarray(np.ascontiguousarray(alpha_png)).save(os.path.join(d, base + '_trans.png'))
        lines.append('\tTextureTranslucency "%s_trans.png"' % rel_path)
        if blend == 2: lines.append('\tg_flAlphaTestReference "0.500"')
    lines += ['\t' + e for e in extra]
    lines += ['\tg_vColorTint "[%.6f %.6f %.6f 0.000000]"' % tuple(tint), '\tg_flModelTintAmount "1.000"', '}']
    open(os.path.join(d, base + '.vmat'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    return rel_path + '.vmat'


def pot(n):
    k = 1
    while k < n: k *= 2
    return k


def quad(mat, p0, p1, p2, p3, uv0, uv1, uv2, uv3, n):
    """two triangles for the quad p0 p1 p2 p3 (counter-clockwise seen from the visible side)"""
    a = p0 + uv0; b = p1 + uv1; c = p2 + uv2; d = p3 + uv3
    return [(mat, (a, b, c), n), (mat, (a, c, d), n)]


def box_tris(mat, x0, y0, z0, x1, y1, z1, uscale=1 / 64.0):
    """closed box seen from outside"""
    t = []
    def q(p0, p1, p2, p3, n, ua, va):
        uv = [((p[ua]) * uscale, (p[va]) * uscale) for p in (p0, p1, p2, p3)]
        t.extend(quad(mat, p0, p1, p2, p3, uv[0], uv[1], uv[2], uv[3], n))
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    q(c[4], c[5], c[6], c[7], (0, 0, 1), 0, 1)      # top
    q(c[3], c[2], c[1], c[0], (0, 0, -1), 0, 1)     # bottom
    q(c[0], c[1], c[5], c[4], (0, -1, 0), 0, 2)     # y0
    q(c[2], c[3], c[7], c[6], (0, 1, 0), 0, 2)      # y1
    q(c[1], c[2], c[6], c[5], (1, 0, 0), 1, 2)      # x1
    q(c[3], c[0], c[4], c[7], (-1, 0, 0), 1, 2)     # x0
    return t


def quad_n(mat, p0, p1, p2, p3, uv0, uv1, uv2, uv3, n):
    """like quad, but flips the winding when needed so the quad faces along n"""
    ax, ay, az = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    bx, by, bz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    cx, cy, cz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
    if cx * n[0] + cy * n[1] + cz * n[2] < 0:
        return quad(mat, p3, p2, p1, p0, uv3, uv2, uv1, uv0, n)
    return quad(mat, p0, p1, p2, p3, uv0, uv1, uv2, uv3, n)


def tri_n(mat, p0, p1, p2, uv0, uv1, uv2, n):
    ax, ay, az = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    bx, by, bz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    cx, cy, cz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
    if cx * n[0] + cy * n[1] + cz * n[2] < 0:
        return [(mat, (p2 + uv2, p1 + uv1, p0 + uv0), n)]
    return [(mat, (p0 + uv0, p1 + uv1, p2 + uv2), n)]


def box_faces(mats, x0, y0, z0, x1, y1, z1, uscale=1 / 256.0):
    """closed box with a material per face direction: mats = dict(top, bottom, x, y) (x: the +-x faces, y: the +-y faces)"""
    t = []
    def q(m, p0, p1, p2, p3, n, ua, va):
        uv = [((p[ua]) * uscale, (p[va]) * uscale) for p in (p0, p1, p2, p3)]
        t.extend(quad_n(m, p0, p1, p2, p3, uv[0], uv[1], uv[2], uv[3], n))
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    q(mats['top'], c[4], c[5], c[6], c[7], (0, 0, 1), 0, 1)
    if mats.get('bottom'): q(mats['bottom'], c[3], c[2], c[1], c[0], (0, 0, -1), 0, 1)
    q(mats['y'], c[0], c[1], c[5], c[4], (0, -1, 0), 0, 2)
    q(mats['y'], c[2], c[3], c[7], c[6], (0, 1, 0), 0, 2)
    q(mats['x'], c[1], c[2], c[6], c[5], (1, 0, 0), 1, 2)
    q(mats['x'], c[3], c[0], c[4], c[7], (-1, 0, 0), 1, 2)
    return t
