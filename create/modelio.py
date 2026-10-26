"""Writes baked meshes as Source 2 content: SMD render/physics meshes, csgo_complex .vmat + PNGs, .vmdl.

From trenchwarfare-cs2/tools/modelio.py (MIT), made project-neutral.
"""
import os, json
import numpy as np
from PIL import Image

def to8(x):
    return (np.clip(x, 0, 1) * 255 + 0.5).astype(np.uint8)


def write_smd(path, mesh, uv, matname):
    """uv: per-vertex (u, v_img); SMD v = 1 - v_img. ModelDoc turns SMD 90 degrees: write (y, -x, z)."""
    V, N = mesh.V, mesh.N
    lines = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0", "0 0 0 0 0 0 0", "end", "triangles"]
    fmt = "0 %.4f %.4f %.4f %.4f %.4f %.4f %.5f %.5f"
    for f in mesh.F:
        lines.append(matname)
        for i in f:
            x, y, z = V[i]; nx, ny, nz = N[i]
            lines.append(fmt % (y, -x, z, ny, -nx, nz, uv[i, 0], 1 - uv[i, 1]))
    lines.append("end")
    open(path, 'w', newline='\n').write("\n".join(lines) + "\n")


def write_hull_smd(path, pts_list):
    """each entry: (k,3) points of one convex piece -> its hull triangles (scipy)"""
    from scipy.spatial import ConvexHull
    lines = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0", "0 0 0 0 0 0 0", "end", "triangles"]
    for pts in pts_list:
        pts = np.asarray(pts, float)
        h = ConvexHull(pts)
        c = pts.mean(0)
        for s, eq in zip(h.simplices, h.equations):
            a, b, cc = pts[s]
            n = np.cross(b - a, cc - a)
            if np.dot(n, eq[:3]) < 0: s = s[::-1]
            lines.append("phys")
            for i in s:
                x, y, z = pts[i]
                lines.append("0 %.3f %.3f %.3f %.3f %.3f %.3f 0 0" % (y, -x, z, eq[1], -eq[0], eq[2]))
    lines.append("end")
    open(path, 'w', newline='\n').write("\n".join(lines) + "\n")


def box_pts(x0, y0, z0, x1, y1, z1, R=None, t=(0, 0, 0)):
    p = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)], float)
    if R is not None: p = p @ np.asarray(R).T
    return p + np.asarray(t, float)


def write_textures(outdir, rel, name, baked, metal=False, size=None):
    d = os.path.join(outdir, rel); os.makedirs(d, exist_ok=True)
    def save(arr, suffix, mode=None):
        im = Image.fromarray(to8(arr))
        if size and im.size[0] != size: im = im.resize((size, size), Image.LANCZOS)
        im.save(os.path.join(d, '%s_%s.png' % (name, suffix)), optimize=True)
        return '%s/%s_%s.png' % (rel, name, suffix)
    t = dict(color=save(baked['color'], 'color'), normal=save(baked['normal'] * 0.5 + 0.5, 'normal'),
             rough=save(baked['rough'], 'rough'), ao=save(baked['ao'], 'ao'))
    if metal: t['metal'] = save(baked['metal'], 'metal')
    return t


def write_vmat(outdir, rel_vmat, tex, comment='', alpha=None, backfaces=False, extra=()):
    lines = ['// %s' % comment, '', 'Layer0', '{', '\tshader "csgo_complex.vfx"', '', '\tF_SPECULAR 1']
    if backfaces: lines.append('\tF_RENDER_BACKFACES 1')
    if alpha:
        lines += ['\tF_ALPHA_TEST 1', '\tTextureTranslucency "%s"' % alpha, '\tg_flAlphaTestReference "0.500"']
    lines += ['\tg_flAmbientOcclusionDirectDiffuse "0.000"', '\tg_flAmbientOcclusionDirectSpecular "0.000"',
              '\tTextureAmbientOcclusion "%s"' % tex['ao'],
              '\tg_flModelTintAmount "1.000"', '\tg_vColorTint "[1.000000 1.000000 1.000000 0.000000]"',
              '\tTextureColor "%s"' % tex['color'], '\tg_bFogEnabled "1"',
              '\tTextureNormal "%s"' % tex['normal'], '\tTextureRoughness "%s"' % tex['rough']]
    if 'metal' in tex:
        lines += ['\tF_METALNESS_TEXTURE 1', '\tTextureMetalness "%s"' % tex['metal']]
    else:
        lines += ['\tg_flMetalness "0.000"']
    lines += ['\t' + e for e in extra]
    lines.append('}')
    p = os.path.join(outdir, rel_vmat); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', newline='\n').write('\n'.join(lines) + '\n')


def _filter():
    return 'import_filter =\n{\nexclude_by_default = false\nexception_list = [  ]\n}'


LOD_SCALE = 16.0         # LOD switches 16x further out than the per-prop values (playtest: swaps visible at ~300 units, then still noticeable at 4x)
# props whose low LOD is not a faithful copy of LOD0 (measured p95 shape deviation >= ~2 units): ship LOD0 only.
# Empty by default; set it from your build script (modelio.SINGLE_LOD.update({...})) or the env var
# CS2_SINGLE_LOD="name1,name2". Example from mg_trenchwarfare: shattered trees, stumps, shelter, wreck_tank.
SINGLE_LOD = {n.strip() for n in os.environ.get('CS2_SINGLE_LOD', '').split(',') if n.strip()}


def vmdl_text(name, rel_dir, meshes, remaps, hulls, surface='default', lod_thresholds=None, archetype='static_prop_model', entity='prop_static', single_lod=None):
    """meshes: list of mesh names (files <rel_dir>/<mesh>.smd), LOD order; remaps: [(from, to)]; single_lod=True keeps LOD0 only"""
    if single_lod or (single_lod is None and name in SINGLE_LOD): meshes = meshes[:1]
    T = '\t'
    out = []
    out.append('<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc41:version{12fc9d44-453a-4ae4-b4d9-7e2ac0bbd4e0} -->')
    out.append('{\n\trootNode =\n\t{\n\t\t_class = "RootNode"\n\t\tchildren =\n\t\t[')
    rm = ''.join('\t\t\t\t\t\t\t{\n\t\t\t\t\t\t\t\tfrom = "%s"\n\t\t\t\t\t\t\t\tto = "%s"\n\t\t\t\t\t\t\t},\n' % r for r in remaps)
    out.append('\t\t\t{\n\t\t\t\t_class = "MaterialGroupList"\n\t\t\t\tchildren =\n\t\t\t\t[\n\t\t\t\t\t{\n\t\t\t\t\t\t_class = "DefaultMaterialGroup"\n'
               '\t\t\t\t\t\tremaps =\n\t\t\t\t\t\t[\n%s\t\t\t\t\t\t]\n\t\t\t\t\t\tuse_global_default = false\n\t\t\t\t\t\tglobal_default_material = ""\n\t\t\t\t\t},\n\t\t\t\t]\n\t\t\t},' % rm)
    rmf = ''
    for m in meshes:
        rmf += ('\t\t\t\t\t{\n\t\t\t\t\t\t_class = "RenderMeshFile"\n\t\t\t\t\t\tname = "%s"\n\t\t\t\t\t\tfilename = "%s/%s.smd"\n\t\t\t\t\t\timport_scale = 1.0\n'
                '\t\t\t\t\t\timport_filter =\n\t\t\t\t\t\t{\n\t\t\t\t\t\t\texclude_by_default = false\n\t\t\t\t\t\t\texception_list = [  ]\n\t\t\t\t\t\t}\n\t\t\t\t\t},\n') % (m, rel_dir, m)
    out.append('\t\t\t{\n\t\t\t\t_class = "RenderMeshList"\n\t\t\t\tchildren =\n\t\t\t\t[\n%s\t\t\t\t]\n\t\t\t},' % rmf)
    if len(meshes) > 1:
        th = [t * LOD_SCALE for t in (lod_thresholds or [0.0] + [20.0 * (2 ** k) for k in range(len(meshes) - 1)])]
        groups = ''
        for m, t in zip(meshes, th):
            groups += ('\t\t\t\t\t{\n\t\t\t\t\t\t_class = "LODGroup"\n\t\t\t\t\t\tmesh_references =\n\t\t\t\t\t\t[\n\t\t\t\t\t\t\t{\n'
                       '\t\t\t\t\t\t\t\tmesh_name = "%s"\n\t\t\t\t\t\t\t\tcopy_and_simplify = false\n\t\t\t\t\t\t\t},\n\t\t\t\t\t\t]\n'
                       '\t\t\t\t\t\tswitch_threshold = %.1f\n\t\t\t\t\t},\n') % (m, t)
        out.append('\t\t\t{\n\t\t\t\t_class = "LODGroupList"\n\t\t\t\tchildren =\n\t\t\t\t[\n%s\t\t\t\t]\n\t\t\t},' % groups)
    if hulls:
        hs = ''
        for h in hulls:
            hs += ('\t\t\t\t\t{\n\t\t\t\t\t\t_class = "PhysicsHullFile"\n\t\t\t\t\t\tname = "%s"\n\t\t\t\t\t\tparent_bone = ""\n\t\t\t\t\t\tsurface_prop = "%s"\n'
                   '\t\t\t\t\t\tcollision_prop = "default"\n\t\t\t\t\t\ttool_material = ""\n\t\t\t\t\t\trecenter_on_parent_bone = false\n'
                   '\t\t\t\t\t\toffset_origin = [ 0.0, 0.0, 0.0 ]\n\t\t\t\t\t\toffset_angles = [ 0.0, 0.0, 0.0 ]\n\t\t\t\t\t\tfilename = "%s/%s.smd"\n'
                   '\t\t\t\t\t\timport_scale = 1.0\n\t\t\t\t\t\tfaceMergeAngle = 10.0\n\t\t\t\t\t\tmaxHullVertices = 0\n\t\t\t\t\t\timport_mode = "SingleHull"\n'
                   '\t\t\t\t\t\tsmall_element_threshold = 0.0\n\t\t\t\t\t\tthin_element_threshold = 0.0\n\t\t\t\t\t\toptimization_algorithm = "QEM"\n'
                   '\t\t\t\t\t\tdisable_region_svm = false\n\t\t\t\t\t\timport_filter =\n\t\t\t\t\t\t{\n\t\t\t\t\t\t\texclude_by_default = false\n'
                   '\t\t\t\t\t\t\texception_list = [  ]\n\t\t\t\t\t\t}\n\t\t\t\t\t},\n') % (h, surface, rel_dir, h)
        out.append('\t\t\t{\n\t\t\t\t_class = "PhysicsShapeList"\n\t\t\t\tchildren =\n\t\t\t\t[\n%s\t\t\t\t]\n\t\t\t\tleave_body_collision_unmodified = false\n\t\t\t\tbody_order = "default"\n\t\t\t},' % hs)
    out.append('\t\t]\n\t\tmodel_archetype = "%s"\n\t\tprimary_associated_entity = "%s"\n\t\tdocument_sub_type = "ModelDocSubType_None"\n\t}\n}\n' % (archetype, entity))
    return '\n'.join(out)
