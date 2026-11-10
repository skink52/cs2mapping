"""Cycles night render of a dumped Sprawl map (see sprawl_preview.py for the three steps and what the picture is and is not).
  blender -b --python tools/arenas/sprawl_preview_bl.py -- <work dir> <content dir>[;<content dir>] <out prefix> <shot>[,<shot>] [samples] [WxH]
"""
import bpy, json, math, os, re, sys
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index('--') + 1:]
WORK, CONTENTS, OUT, SHOTS_ARG = argv[0], argv[1].split(';'), argv[2], argv[3].split(',')
SAMPLES = int(argv[4]) if len(argv) > 4 else 96
RES = tuple(int(v) for v in argv[5].split('x')) if len(argv) > 5 else (1600, 900)

SHOTS = {   # name: (eye, target, lens mm)
    'square': ((2500, -2900, 1650), (0, 100, 380), 26),
    'square_low': ((1250, -2080, 300), (-150, 300, 560), 22),
    'square_side': ((2330, -1500, 190), (1700, 600, 220), 24),
    'avenue': ((4380, 150, 250), (1800, -40, 330), 24),
    'sidewalk': ((3330, -2030, 62), (3900, -1990, 70), 20),
    'avenue_s': ((3150, -2500, 230), (600, -2330, 260), 24),
    'deck': ((1650, 2330, 1120), (-2400, 2420, 900), 24),
    'under': ((1150, 2180, 210), (-1400, 2500, 330), 22),
    'roofs': ((5200, -5200, 3600), (800, -800, 600), 30),
    'top': ((0, -1, 11000), (0, 0, 0), 60),
}


def find(rel):
    for c in CONTENTS:
        p = os.path.join(c, *rel.split('/'))
        if os.path.exists(p): return p
    return None


def node_mat(name, guess):
    mat = bpy.data.materials.new(name[-60:]); mat.use_nodes = True
    nt = mat.node_tree; bsdf = nt.nodes['Principled BSDF']; out = nt.nodes['Material Output']
    base = name[:-5] if name.endswith('.vmat') else name
    color = find(base + '_color.png')
    low = name.lower()
    if color:
        vm = open(find(base + '.vmat'), encoding='utf-8').read() if find(base + '.vmat') else ''
        tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(color, check_existing=True)
        nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        rough = find(base + '_rough.png')
        r = 0.5
        if rough:
            im = bpy.data.images.load(rough, check_existing=True); px = im.pixels[0:4]; r = px[0] ** (1 / 2.2) if im.colorspace_settings.name == 'sRGB' else px[0]
        bsdf.inputs['Roughness'].default_value = max(0.03, min(1.0, r))
        g = re.search(r'g_flMetalness "([\d.]+)"', vm)
        if g: bsdf.inputs['Metallic'].default_value = float(g.group(1))
        illum = find(base + '_illum.png')
        if illum and 'F_SELF_ILLUM' in vm:
            g = re.search(r'g_flSelfIllumBrightness "([\d.]+)"', vm); glow = float(g.group(1)) if g else 1.0
            it = nt.nodes.new('ShaderNodeTexImage'); it.image = bpy.data.images.load(illum, check_existing=True); it.image.colorspace_settings.name = 'Non-Color'
            mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = glow * 2.2
            nt.links.new(it.outputs['Color'], mul.inputs[0])
            nt.links.new(tex.outputs['Color'], bsdf.inputs['Emission Color']); nt.links.new(mul.outputs[0], bsdf.inputs['Emission Strength'])
        alpha = find(base + '_alpha.png')
        if alpha and ('F_ALPHA_TEST' in vm or 'F_TRANSLUCENT' in vm):
            at = nt.nodes.new('ShaderNodeTexImage'); at.image = bpy.data.images.load(alpha, check_existing=True); at.image.colorspace_settings.name = 'Non-Color'
            if 'F_ALPHA_TEST' in vm:
                gt = nt.nodes.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = 0.5
                nt.links.new(at.outputs['Color'], gt.inputs[0]); nt.links.new(gt.outputs[0], bsdf.inputs['Alpha'])
            else: nt.links.new(at.outputs['Color'], bsdf.inputs['Alpha'])
        return mat
    c = [v / 255.0 for v in guess]
    wet = any(k in low for k in ('asphalt', 'concrete_floor', 'floor'))
    if 'liquids' in low or 'water' in low:
        bsdf.inputs['Base Color'].default_value = (0.012, 0.02, 0.03, 1); bsdf.inputs['Roughness'].default_value = 0.04; bsdf.inputs['Alpha'].default_value = 0.82
    elif 'windows' in low and 'lit' in low:
        bsdf.inputs['Base Color'].default_value = (0.3, 0.3, 0.3, 1); bsdf.inputs['Emission Color'].default_value = (1, 0.8, 0.5, 1); bsdf.inputs['Emission Strength'].default_value = 1.5
    else:
        k = 0.42 if 'asphalt' in low else 0.6
        bsdf.inputs['Base Color'].default_value = (c[0] ** 2.2 * k, c[1] ** 2.2 * k, c[2] ** 2.2 * k, 1)
        bsdf.inputs['Roughness'].default_value = 0.22 if wet else 0.6
        if 'metal' in low or 'steel' in low: bsdf.inputs['Metallic'].default_value = 0.6
    return mat


def build_map():
    d = np.load(os.path.join(WORK, 'map.npz')); info = json.load(open(os.path.join(WORK, 'materials.json')))
    verts, uvs, sizes, matidx = d['verts'], d['uvs'], d['sizes'], d['matidx']
    starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32)
    me = bpy.data.meshes.new('map')
    me.vertices.add(len(verts)); me.vertices.foreach_set('co', verts.ravel())
    me.loops.add(len(verts)); me.loops.foreach_set('vertex_index', np.arange(len(verts), dtype=np.int32))
    me.polygons.add(len(sizes)); me.polygons.foreach_set('loop_start', starts)
    try: me.polygons.foreach_set('loop_total', sizes)
    except Exception: pass
    me.polygons.foreach_set('material_index', matidx)
    uvl = me.uv_layers.new(name='uv'); flip = uvs.copy(); flip[:, 1] = 1.0 - flip[:, 1]; uvl.data.foreach_set('uv', flip.ravel())
    for n, g in zip(info['materials'], info['guess']): me.materials.append(node_mat(n, g))
    me.update(calc_edges=True); me.validate()
    ob = bpy.data.objects.new('map', me); bpy.context.scene.collection.objects.link(ob)
    print('map: %d faces, %d materials' % (len(sizes), len(info['materials'])))


def rot(ang):
    p, y, r = [math.radians(a) for a in ang]
    sp, cp, sy, cy, sr, cr = math.sin(p), math.cos(p), math.sin(y), math.cos(y), math.sin(r), math.cos(r)
    return Matrix([[cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy], [cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy], [-sp, sr * cp, cr * cp]])


def build_props():
    pp = os.path.join(WORK, 'prop_meshes.json')
    if not os.path.exists(pp): return
    meshes = json.load(open(pp)); props = json.load(open(os.path.join(WORK, 'props.json')))
    body = bpy.data.materials.new('prop_body'); body.use_nodes = True
    nt = body.node_tree; b = nt.nodes['Principled BSDF']; oi = nt.nodes.new('ShaderNodeObjectInfo')
    nt.links.new(oi.outputs['Color'], b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.4; b.inputs['Metallic'].default_value = 0.25
    glass = bpy.data.materials.new('prop_glass'); glass.use_nodes = True
    g = glass.node_tree.nodes['Principled BSDF']; g.inputs['Base Color'].default_value = (0.02, 0.03, 0.04, 1); g.inputs['Roughness'].default_value = 0.05
    leaf = bpy.data.materials.new('prop_leaf'); leaf.use_nodes = True
    leaf.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.03, 0.08, 0.03, 1)
    cache = {}; n = 0
    for p in props:
        m = p['model']
        if m not in meshes: continue
        if m not in cache:
            V, F, MI = [], [], []
            for dc in meshes[m]:
                o = len(V); P_ = dc['P']; I = dc['I']
                V += [(P_[i], P_[i + 1], P_[i + 2]) for i in range(0, len(P_), 3)]
                F += [(I[i] + o, I[i + 1] + o, I[i + 2] + o) for i in range(0, len(I), 3)]
                low = dc['material'].lower(); MI += [1 if 'glass' in low else 2 if ('leaf' in low or 'leaves' in low or 'foliage' in low or 'tree' in low) else 0] * (len(I) // 3)
            me = bpy.data.meshes.new(m.split('/')[-1]); me.from_pydata(V, [], F)
            for mm in (body, glass, leaf): me.materials.append(mm)
            me.polygons.foreach_set('material_index', MI); me.update(); cache[m] = me
        ob = bpy.data.objects.new(cache[m].name, cache[m]); bpy.context.scene.collection.objects.link(ob)
        s = p['scale']; M4 = rot(p['angles']).to_4x4(); M4.translation = Vector(p['origin'])
        ob.matrix_world = M4 @ Matrix.Diagonal((s[0], s[1], s[2], 1.0))
        t = [int(v) / 255.0 for v in p['tint'].split()[:3]]
        base = (0.55, 0.55, 0.55) if ('tree' in m or 'crane' in m) else (0.42, 0.42, 0.42)
        ob.color = (t[0] ** 2.2 * base[0], t[1] ** 2.2 * base[1], t[2] ** 2.2 * base[2], 1.0); n += 1
    print('props: %d of %d models' % (n, len(cache)))


def build_lights():
    lights = json.load(open(os.path.join(WORK, 'lights.json')))
    for i, l in enumerate(lights):
        ld = bpy.data.lights.new('l%d' % i, 'POINT'); c = [int(v) / 255.0 for v in l['color'].split()[:3]]
        ld.color = c; ld.energy = l["lumens"] * 260.0; ld.shadow_soft_size = 12.0
        ob = bpy.data.objects.new('l%d' % i, ld); ob.location = l['origin']; bpy.context.scene.collection.objects.link(ob)
    print('lights: %d' % len(lights))


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    build_map(); build_props(); build_lights()
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.035, 0.04, 0.085, 1); bg.inputs[1].default_value = 0.5
    sc.render.engine = 'CYCLES'; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for dev in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI'):
        try:
            prefs.compute_device_type = dev; prefs.get_devices()
            got = [d for d in prefs.devices if d.type == dev]
            if got:
                for d in prefs.devices: d.use = (d.type == dev)
                sc.cycles.device = 'GPU'; print('cycles on', dev, [d.name for d in got]); break
        except Exception: pass
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.exposure = 0.0
    try: sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception: pass
    sc.cycles.max_bounces = 4; sc.cycles.sample_clamp_indirect = 8.0
    cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
    cd.clip_start = 4.0; cd.clip_end = 60000.0
    for shot in SHOTS_ARG:
        eye, tgt, lens = SHOTS[shot]
        cam.location = eye; d = Vector(tgt) - Vector(eye); cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); cd.lens = lens
        sc.render.filepath = '%s_%s.png' % (OUT, shot)
        bpy.ops.render.render(write_still=True); print('rendered', sc.render.filepath)


main()
