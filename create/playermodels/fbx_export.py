"""Blender script: a rigged humanoid FBX or GLB (Mixamo / Unreal / Riot style bone names, as The Models Resource rips carry) ->
<out>.npz for the converter, with the skeleton renamed to GMod's ValveBiped names so gmod2cs2 treats it like any GMod player model.

    blender -b --factory-startup -P fbx_export.py -- <model.fbx|.glb> <out.npz> [--drop material,material] [--drop-bones regex] [--fold-bones regex] [--drop-orphans]

--drop leaves out the triangles of those materials (props lying at the feet, a weapon held in the bind pose); --drop-bones leaves out
triangles with a vertex mostly (> 50 %) skinned to bones whose name matches (tails or wings CS2 can't move: Ahri's '.*Tail.*').
--fold-bones keeps them instead: each matching chain is swung from its root to hang back and down behind the body (its curl kept), the
mesh baked in that pose, and the chain then rides rigidly on its nearest mapped parent (pelvis for tails), like a hat on the head.
--drop-orphans leaves out parts mostly skinned to bones with no body bone above them (Riot: weapons and props hung off the root,
which would float where the bind pose left them: Aatrox's sword, Caitlyn's rifle, Annie's Tibbers). A CS2 player holds CS2 weapons.

Meshes with no skin weights (stray spheres, markers) are left out when the file has an armature. Textures a material carries in its
nodes (GLB: embedded) are saved beside the npz as <material>_color.png / _normal.png / _alpha.png and listed in 'textures' (JSON);
fbxprep.py uses them when there is no .mtl. glTF normal maps are OpenGL (Y+): flipped to Source's Y- here.

Writes (Source units, inches; z up; v from the top like a VVD):
  names, parents, world (n,3,4 bone -> model, reference pose), V, N, UV, W, B (3 weights per vertex, like a VVD), tris (k,3),
  tri_mat (k,), materials (names). Prints the bone mapping and any main bone it could not find. srcmdl.SrcModel reads the npz.
Bones it doesn't map (face, hair, props) keep their names; the converter moves them with their nearest mapped parent.
"""
import bpy, re, sys
from mathutils import Vector
import numpy as np

INCH = 1 / 0.0254
SIDE = {'left': 'L', 'right': 'R'}
FINGER = {'thumb': 0, 'index': 1, 'middle': 2, 'ring': 3, 'pinky': 4}


def side_rest(n):
    """'LeftArm' / 'L_Shoulder' / 'l_hand' -> ('L', 'arm'); None when the bone has no side"""
    n = re.sub(r'^.*[:|]', '', n)
    m = re.match(r'(?i)(left|right)_?(.*)$', n) or re.match(r'([LRlr])_(.*)$', n)
    if not m: return None
    return ('L' if m.group(1).lower()[0] == 'l' else 'R'), m.group(2).lower().replace('_', '')


def vb_name(n, spines, riot, leg_is_thigh=False):
    """bone name -> ValveBiped name (or None). riot: the skeleton has its own clavicle, so 'shoulder' is the upper arm (Riot:
    Clavicle, Shoulder, Elbow, Hand; Hip, KneeUpper, Foot, Toe) rather than Mixamo's clavicle"""
    k = re.sub(r'^.*[:|]', '', n).lower()
    k = re.sub(r'^c_', '', k).replace('_', '')                      # Vladimir: C_Hip, C_Waist (C = centre)
    base = {'pevis': 'Pelvis', 'hips': 'Pelvis', 'pelvis': 'Pelvis', 'hip': 'Pelvis', 'waist': 'Pelvis', 'neck': 'Neck1', 'neck1': 'Neck1', 'head': 'Head1'}
    if k in base: return 'ValveBiped.Bip01_' + base[k]
    if k in spines: return 'ValveBiped.Bip01_' + spines[k]
    sr = side_rest(n)
    if not sr: return None
    s, rest = sr
    part = {'shoulder': 'UpperArm' if riot else 'Clavicle', 'clavicle': 'Clavicle', 'arm': 'UpperArm', 'upperarm': 'UpperArm',
            'uparm': 'UpperArm', 'forearm': 'Forearm', 'elbow': 'Forearm', 'lowarm': 'Forearm', 'hand': 'Hand', 'upleg': 'Thigh', 'thigh': 'Thigh', 'hip': 'Thigh',
            'leg': 'Thigh' if leg_is_thigh else 'Calf', 'calf': 'Calf', 'forarm': 'Forearm', 'kneeupper': 'Calf', 'knee': 'Calf', 'foot': 'Foot', 'toebase': 'Toe0', 'toe': 'Toe0',
            'armroll': 'Bicep', 'shouldertwist': 'Bicep', 'forearmroll': 'Ulna', 'handtwist': 'Ulna', 'uplegroll': 'Quad'}
    part = part.get(rest) or (part.get(rest[:-1]) if rest.endswith('1') else None)        # Blitzcrank: L_uparm1
    if part: return 'ValveBiped.Bip01_%s_%s' % (s, part)
    f = re.match(r'(?:hand)?(?:finger)?(thumb|index|middle|ring|pinky)([123abc]?)(?:jnt)?$', rest)    # Index1-3, index/_b/_c, _jnt
    if f:
        seg = {'': 0, '1': 0, 'a': 0, '2': 1, 'b': 1, '3': 2, 'c': 2}[f.group(2)]
        return 'ValveBiped.Bip01_%s_Finger%d%s' % (s, FINGER[f.group(1)], ('', '1', '2')[seg])
    return None


def node_images(mat):
    """{'color' / 'normal' / 'alpha': bpy image} from a material's node tree (Principled BSDF inputs)"""
    out = {}
    if not mat or not mat.use_nodes: return out
    def img_from(sock, depth=0):
        if not sock.is_linked or depth > 4: return None
        nd = sock.links[0].from_node
        if nd.type == 'TEX_IMAGE': return nd.image
        for i in nd.inputs:
            im = img_from(i, depth + 1)
            if im: return im
        return None
    for nd in mat.node_tree.nodes:
        if nd.type != 'BSDF_PRINCIPLED': continue
        for key, sock in (('color', 'Base Color'), ('normal', 'Normal'), ('alpha', 'Alpha')):
            if sock in nd.inputs:
                im = img_from(nd.inputs[sock])
                if im: out[key] = im
    if 'color' not in out:                   # unlit materials (glTF KHR_materials_unlit): no Principled BSDF, the image feeds an emission mix
        im = next((nd.image for nd in mat.node_tree.nodes if nd.type == 'TEX_IMAGE' and nd.image), None)
        if im: out['color'] = im
    return out


def fold(arm, rx):
    """swing every chain of bones matching rx (from its first matching bone) to point back and down, keeping a little of its
    sideways spread; children follow. Front is found from the feet (toe - foot), else -Y (glTF imports face -Y)."""
    from mathutils import Matrix
    pb = arm.pose.bones
    names = [b.name for b in arm.data.bones]
    def find(*keys):
        for b in arm.data.bones:
            k = b.name.lower().replace('_', '')
            if any(k.endswith(x) for x in keys): return b
    toe, foot = find('lefttoebase', 'ltoe', 'lefttoe'), find('leftfoot', 'lfoot')
    fwd = Vector((0, -1, 0))
    if toe and foot:
        f = (toe.head_local - foot.head_local); f.z = 0
        if f.length > 1e-4: fwd = f.normalized()
    back, down = -fwd, Vector((0, 0, -1))
    def kids(b): return [c for c in b.children if rx.fullmatch(c.name)]
    roots, todo = [], [b for b in arm.data.bones if rx.fullmatch(b.name) and not (b.parent and rx.fullmatch(b.parent.name))]
    while todo:                          # a hub several chains branch from (Ahri's nine tails share one) is not swung: its branches are
        b = todo.pop()
        if len(kids(b)) > 1: todo += kids(b)
        else: roots.append(b)
    for b in roots:
        tips = [c for c in b.children_recursive] or [b]
        tip = max(tips, key=lambda c: (c.tail_local - b.head_local).length)
        d = (tip.tail_local - b.head_local)
        if d.length < 1e-4: continue
        side = d - back * d.dot(back); side.z = 0
        target = (back * 0.7 + down * 0.6 + (side.normalized() * 0.25 if side.length > 1e-4 else Vector())).normalized()
        q = d.normalized().rotation_difference(target)
        h = b.head_local
        M = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h)
        p = pb[b.name]
        p.matrix = M @ p.matrix
        bpy.context.view_layer.update()
    print('  folded %d chains back and down (%s)' % (len(roots), rx.pattern))


def main():
    a = sys.argv[sys.argv.index('--') + 1:]
    src, out = a[0], a[1]
    drop = set(a[a.index('--drop') + 1].split(',')) if '--drop' in a else set()
    drop_bones = re.compile(a[a.index('--drop-bones') + 1], re.I) if '--drop-bones' in a else None
    drop_orphans = '--drop-orphans' in a
    fold_bones = re.compile(a[a.index('--fold-bones') + 1], re.I) if '--fold-bones' in a else None
    bpy.ops.wm.read_factory_settings(use_empty=True)
    gltf = src.lower().endswith(('.glb', '.gltf'))
    if gltf: bpy.ops.import_scene.gltf(filepath=src)
    else: bpy.ops.import_scene.fbx(filepath=src)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    meshes = []
    for o in bpy.data.objects:
        if o.type != 'MESH' or not len(o.data.vertices): continue
        if not o.vertex_groups: print('  left out unskinned mesh %s (%d vertices)' % (o.name, len(o.data.vertices))); continue
        meshes.append(o)
    bones = list(arm.data.bones)
    if fold_bones: fold(arm, fold_bones)
    deps = bpy.context.evaluated_depsgraph_get()
    keys = [re.sub(r'^.*[:|]', '', b.name).lower().replace('_', '') for b in bones]
    sides = [(side_rest(b.name) or ('', ''))[1] for b in bones]
    leg_is_thigh = 'calf' in sides and not any(x in sides for x in ('thigh', 'upleg', 'hip'))   # Shaco: L_leg + L_calf
    riot = any((side_rest(b.name) or ('', ''))[1] == 'clavicle' for b in bones)
    sp = sorted(k for k in keys if re.fullmatch(r'spine\d?', k))     # spine, spine1, spine2 (, spine3): onto Spine .. Spine4
    if 'chest' in keys: sp.append('chest')                              # Riot: Spine1, Spine2, Chest
    target = {1: ['Spine'], 2: ['Spine', 'Spine4'], 3: ['Spine', 'Spine2', 'Spine4'], 4: ['Spine', 'Spine1', 'Spine2', 'Spine4']}.get(len(sp), [])
    spines = dict(zip(sp, target))
    if not any(k in ('hips', 'pelvis', 'hip', 'waist') for k in keys) and len(sp) >= 2:   # no pelvis bone (Annie, Elise): the lowest spine is it
        spines = dict(zip(sp, ['Pelvis'] + {1: ['Spine'], 2: ['Spine', 'Spine4'], 3: ['Spine', 'Spine2', 'Spine4']}.get(len(sp) - 1, [])))
    names, used = [], set()
    for b in bones:
        v = vb_name(b.name, spines, riot, leg_is_thigh)
        if v and v not in used: used.add(v); names.append(v); print('  %-28s -> %s' % (b.name, v))
        else: names.append(b.name)
    for need in ('Pelvis', 'L_Thigh', 'R_Thigh', 'L_UpperArm', 'R_UpperArm', 'Head1', 'L_Hand', 'R_Hand', 'L_Foot', 'R_Foot'):
        if 'ValveBiped.Bip01_' + need not in used: print('  MISSING main bone', need)
    index = {b.name: i for i, b in enumerate(bones)}
    def body_above(b):
        while b is not None:
            if names[index[b.name]].startswith('ValveBiped.'): return True
            b = b.parent
        return False
    orphans = {b.name for b in bones if not body_above(b)}
    parents = [index[b.parent.name] if b.parent else -1 for b in bones]
    lower = {b.name.lower(): i for i, b in enumerate(bones)}
    for i, b in enumerate(bones):      # Riot '<bone>_SNAP' helpers (skinned, parented to the root) follow their base bone in game
        m = re.match(r'(?i)(.+)_snap$', b.name)
        if m and m.group(1).lower() in lower:
            parents[i] = lower[m.group(1).lower()]; print('  %-28s follows %s' % (b.name, m.group(1)))
    world = []
    for b in bones:
        M = arm.matrix_world @ b.matrix_local
        R = np.array(M.to_3x3().normalized()); t = np.array(M.translation) * INCH
        world.append(np.hstack([R, t[:, None]]))
    V, N, UV, W, B, tris, tmat, mats = [], [], [], [], [], [], [], []
    for o in meshes:
        me = o.data
        ev = o.evaluated_get(deps).data if fold_bones else me        # folded chains: the posed (armature-deformed) positions
        me.calc_loop_triangles()
        uvl = me.uv_layers.active.data if me.uv_layers.active else None
        cn = me.corner_normals if hasattr(me, 'corner_normals') else None
        Mw = o.matrix_world; R3 = Mw.to_3x3()
        gname = {g.index: g.name for g in o.vertex_groups}
        vw, dropv = [], []
        for v in me.vertices:
            if drop_bones or drop_orphans:
                gs = [(g.weight, gname.get(g.group, '')) for g in v.groups if g.weight > 0]
                t_ = sum(w for w, _ in gs) or 1.0
                dropv.append(sum(w for w, nm in gs if (drop_bones and drop_bones.fullmatch(nm)) or (drop_orphans and nm in orphans)) / t_)
            ws = sorted(((g.weight, index[gname[g.group]]) for g in v.groups if g.group in gname and gname[g.group] in index and g.weight > 0),
                        reverse=True)[:3]
            if not ws: ws = [(1.0, index.get(o.parent_bone) or 0)]
            tot = sum(w for w, _ in ws)
            vw.append((([w / tot for w, _ in ws] + [0, 0, 0])[:3], ([j for _, j in ws] + [0, 0, 0])[:3]))
        mbase = len(mats)
        mats += [m.name if m else 'default' for m in me.materials] or ['default']
        key = {}
        for lt in me.loop_triangles:
            if me.materials and lt.material_index < len(me.materials) and me.materials[lt.material_index] and me.materials[lt.material_index].name in drop: continue
            if dropv and any(dropv[vi] > 0.5 for vi in lt.vertices): continue
            tri = []
            for vi, li in zip(lt.vertices, lt.loops):
                uv = tuple(round(x, 5) for x in uvl[li].uv) if uvl else (0.0, 0.0)
                n = tuple(round(x, 3) for x in (cn[li].vector if cn else me.vertices[vi].normal))
                k = (vi, uv, n)
                if k not in key:
                    key[k] = len(V)
                    V.append(np.array(Mw @ ev.vertices[vi].co) * INCH)
                    nn = np.array(R3 @ Vector(n)); N.append(nn / (np.linalg.norm(nn) or 1))
                    UV.append((uv[0], 1 - uv[1])); W.append(vw[vi][0]); B.append(vw[vi][1])
                tri.append(key[k])
            tris.append(tri); tmat.append(mbase + min(lt.material_index, len(me.materials) - 1 if me.materials else 0))
    import json, os
    tex, tdir = {}, os.path.dirname(os.path.abspath(out))
    for o in meshes:
        for m in o.data.materials:
            if not m or m.name in tex: continue
            got = {}
            for key, im in node_images(m).items():
                path = os.path.join(tdir, re.sub(r'[^A-Za-z0-9_]', '_', m.name).lower() + '_' + key + '.png')
                w, h = im.size
                px = np.array(im.pixels[:], np.float32).reshape(h, w, 4)[::-1]
                if key == 'normal' and gltf: px[..., 1] = 1 - px[..., 1]        # OpenGL -> Source's DirectX-style normal map
                tmp = bpy.data.images.new('x_' + key, w, h, alpha=True)     # Blender's Python has no PIL: save through bpy
                tmp.pixels[:] = px[::-1].ravel(); tmp.filepath_raw = path; tmp.file_format = 'PNG'; tmp.save()
                got[key] = os.path.basename(path)
            tex[m.name] = got
            print('  material %s: %s' % (m.name, ', '.join(got) or 'no textures'))
    np.savez_compressed(out, drop=np.array(','.join(sorted(drop)) + ('|' + drop_bones.pattern if drop_bones else '') + ('^' + fold_bones.pattern if fold_bones else '') + ('~orphans' if drop_orphans else '')), textures=np.array(json.dumps(tex)), names=np.array(names), parents=np.array(parents), world=np.array(world), V=np.array(V), N=np.array(N),
                        UV=np.array(UV), W=np.array(W), B=np.array(B, np.int32), tris=np.array(tris, np.int64), tri_mat=np.array(tmat),
                        materials=np.array(mats))
    print('wrote %s: %d bones, %d vertices, %d triangles, %d materials' % (out, len(names), len(V), len(tris), len(mats)))


main()
