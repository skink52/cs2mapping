"""Cut an over-dense converted prop's LOD0 to a triangle budget (remaster step 14: the 28.9k-triangle petrol can, the 27.5k Stahlhelm
pair, the 18.6k field telephone), keeping its materials, UV layout (so the existing textures still fit), scale, origin and footprint.

Blender does the work, headless (`blender -b --factory-startup --python-exit-code 1 --python <this file> -- ...`, no window): the SMD
is read here as text, welded by position (UV seams stay as per-corner UVs), decimated with the Collapse decimator (quadric edge
collapse; UV seams and material borders are weighted so they hold), triangulated, then written back as an SMD with per-corner
normals smoothed within 40 degrees (hard edges stay hard). Then tools/lod_decimate.py builds LOD1-4 from the new LOD0 as usual.

usage: python tools/decimate_lod0.py <in.smd> <out.smd> <target tris> [--blender <blender.exe>] [--angle 40]
Reads the input (never writes it). Level: checked by render + bounds (unchanged within 0.1 u); compiled in the scratch addon.
"""
import os, subprocess, sys

BLENDER = os.environ.get('BLENDER', r'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe')


def read_smd(path):
    """-> (head lines, [(material, [(x, y, z, nx, ny, nz, u, v)] * 3)])"""
    L = open(path, errors='ignore').read().split('\n')
    i = L.index('triangles'); head = L[:i + 1]; i += 1
    tris = []
    while i < len(L) and L[i].strip() != 'end':
        mat = L[i].strip()
        vs = [tuple(float(x) for x in L[i + 1 + k].split()[1:9]) for k in range(3)]
        tris.append((mat, vs)); i += 4
    return head, tris


def blender_main(argv):
    import bpy, bmesh
    from mathutils import Vector
    src, dst, target, angle = argv[0], argv[1], int(argv[2]), float(argv[3])
    head, tris = read_smd(src)
    mats = sorted({m for m, _ in tris})
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('uv')
    vmap = {}
    def vert(p):
        k = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
        if k not in vmap: vmap[k] = bm.verts.new(k)
        return vmap[k]
    for mat, vs in tris:
        vv = [vert(v) for v in vs]
        if len({id(x) for x in vv}) < 3: continue
        try: f = bm.faces.new(vv)
        except ValueError: continue          # a duplicate face
        f.material_index = mats.index(mat)
        for loop, v in zip(f.loops, vs): loop[uvl].uv = (v[6], v[7])
    me = bpy.data.meshes.new('lod0'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('lod0', me); bpy.context.scene.collection.objects.link(ob)
    for m in mats: me.materials.append(bpy.data.materials.new(m))
    bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    n0 = len(me.polygons)
    mod = ob.modifiers.new('dec', 'DECIMATE'); mod.decimate_type = 'COLLAPSE'; mod.use_collapse_triangulate = True
    mod.ratio = min(1.0, target / max(n0, 1))
    mod.delimit = {'MATERIAL', 'SEAM', 'UV'} if hasattr(mod, 'delimit') else None
    bpy.ops.object.modifier_apply(modifier='dec')
    tri = ob.modifiers.new('tri', 'TRIANGULATE'); bpy.ops.object.modifier_apply(modifier='tri')
    me = ob.data
    # per-corner normals: smooth within `angle`, hard beyond
    import math
    try:
        me.set_sharp_from_angle(angle=math.radians(angle))
    except AttributeError:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))
    cn = [tuple(c.vector) for c in me.corner_normals] if hasattr(me, 'corner_normals') else None
    uv = me.uv_layers[0].data
    out = head[:]
    for p in me.polygons:
        out.append(mats[p.material_index])
        for li in p.loop_indices:
            lp = me.loops[li]; co = me.vertices[lp.vertex_index].co
            n = cn[li] if cn else tuple(lp.normal)
            u, v = uv[li].uv
            out.append('0 %.4f %.4f %.4f %.4f %.4f %.4f %.5f %.5f' % (co.x, co.y, co.z, n[0], n[1], n[2], u, v))
    out.append('end')
    open(dst, 'w', newline='\n').write('\n'.join(out) + '\n')
    print('decimate_lod0: %s %d -> %d triangles' % (os.path.basename(src), n0, len(me.polygons)))


def main(argv):
    a = [x for x in argv]
    bl = BLENDER; angle = '40'
    if '--blender' in a: i = a.index('--blender'); bl = a[i + 1]; del a[i:i + 2]
    if '--angle' in a: i = a.index('--angle'); angle = a[i + 1]; del a[i:i + 2]
    if len(a) != 3: print(__doc__); return 2
    src, dst, target = a
    if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)): sys.exit('decimate_lod0: out must differ from the input')
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    cmd = [bl, '-b', '--factory-startup', '--python-exit-code', '1', '--python', os.path.abspath(__file__), '--',
           '--in-blender', os.path.abspath(src), os.path.abspath(dst), str(int(target)), angle]
    flags = 0x08000000 if os.name == 'nt' else 0          # CREATE_NO_WINDOW: never a console popping over a fullscreen game
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=flags)
    for line in (r.stdout + r.stderr).splitlines():
        if 'decimate_lod0' in line or 'Error' in line or 'Traceback' in line or line.startswith('  '): print(line)
    return r.returncode


if __name__ == '__main__':
    if '--in-blender' in sys.argv:
        blender_main(sys.argv[sys.argv.index('--in-blender') + 1:])
    else:
        sys.exit(main(sys.argv[1:]))
