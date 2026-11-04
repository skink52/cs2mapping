"""Animated (flipbook) textures on tiled faces -> skinned prop_dynamic models stepped by the io script (stage D pass `animprops`).

  python animprops.py <vmap in> <vmap out> <addon content dir> <addon> <spec> [<spec> ...]
  spec:  <key>=<material substring>:<sheet png>:<columns>:<frames>:<fps>[:alpha]

CS2's F_TEXTURE_ANIMATION offsets the UV by one sheet cell per frame but never wraps inside the cell, so a tiled face (UV span
over 1) shows a window of the whole sheet that steps across it. Verified on mg_minecraft_adventure's fire and lava (4 Nov 2026).
Hellmatch's route works instead: every frame is its own material, the model has one material group per frame, and a script
steps the `Skin` input.

What this does, per spec:
- cuts the sheet (row-major cells of 128 px, or sheet width / columns) into `materials/port_anim/<key>/f_NN` unlit vmats
  (`csgo_unlitgeneric`, both sides drawn; `alpha` = alpha-tested, the sheet's alpha or a `<sheet>_trans.png` next to it);
- every face whose material contains the substring is copied into a model (SMD + vmdl, `models/port_anim/<addon>_<key>_<n>.vmdl`),
  one model per owner: all world / static faces together (origin at their centre), and one per moving entity (func_tracktrain,
  func_door, func_movelinear, func_rotating, func_physbox, named func_brush), with the model origin at the entity's origin so the
  script can glue it on; faces keep their tiling UVs; the vmdl gets a material group per frame (`Skin` k = frame k);
- the original faces become toolsnodraw (collision and triggers unchanged);
- a `prop_dynamic` per model (`port_anim_<key>_<n>`, non-solid, no shadows);
- `maps/scripts/<addon>_io.js` gets a `port_anim` section: at round start the props of moving owners are teleported onto the owner
  (which may have moved to its first path_track at spawn) and parented; a thinker sends `Skin` whenever the frame changes.
"""
import math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx
import vmapedit as V
from texfix import stream

NODRAW = 'materials/tools/toolsnodraw.vmat'
MOVERS = ('func_tracktrain', 'func_door', 'func_door_rotating', 'func_movelinear', 'func_rotating', 'func_physbox', 'func_physbox_multiplayer',
          'func_tanktrain', 'func_platrot', 'func_train')
MARK_A, MARK_B = '// ---------------------------------------------------------------- port_anim (animprops.py)', '// ---------------------------------------------------------------- end port_anim'


def parse_spec(s):
    key, rest = s.split('=', 1)
    sub, rest = rest.split(':', 1)
    p = rest.split(':')
    alpha = p[-1] == 'alpha'
    if alpha: p = p[:-1]
    cols, frames, fps = int(p[-3]), int(p[-2]), float(p[-1])
    return {'key': key, 'sub': sub.lower(), 'sheet': ':'.join(p[:-3]), 'cols': cols, 'frames': frames, 'fps': fps, 'alpha': alpha}


def cut_frames(content, spec):
    from PIL import Image
    im = Image.open(spec['sheet']).convert('RGBA')
    w, h = im.size
    cell = w // spec['cols']
    trans = None
    tp = os.path.splitext(spec['sheet'])[0] + '_trans.png'
    if spec['alpha'] and os.path.exists(tp): trans = Image.open(tp).convert('L')
    d = os.path.join(content, 'materials', 'port_anim', spec['key'])
    os.makedirs(d, exist_ok=True)
    paths = []
    for k in range(spec['frames']):
        x, y = (k % spec['cols']) * cell, (k // spec['cols']) * cell
        fr = im.crop((x, y, x + cell, y + cell))
        base = 'f_%02d' % k
        rel = 'materials/port_anim/%s/%s' % (spec['key'], base)
        fr.convert('RGB').save(os.path.join(d, base + '_color.png'))
        lines = ['// %s frame %d of %d (animprops.py)' % (spec['key'], k, spec['frames']), 'Layer0', '{', '\tshader "csgo_unlitgeneric.vfx"',
                 '\tF_RENDER_BACKFACES 1', '\tTextureColor "%s_color.png"' % rel]
        if spec['alpha']:
            a = trans.crop((x, y, x + cell, y + cell)) if trans is not None else fr.getchannel('A')
            a.save(os.path.join(d, base + '_trans.png'))
            lines += ['\tF_BLEND_MODE 2', '\tTextureTranslucency "%s_trans.png"' % rel, '\tg_flAlphaTestReference "0.500"']
        else:
            lines.append('\tF_BLEND_MODE 0')
        lines += ['\tg_vColorTint "[1.000000 1.000000 1.000000 0.000000]"', '\tg_flModelTintAmount "1.000"', '}']
        open(os.path.join(d, base + '.vmat'), 'w', newline='\n').write('\n'.join(lines) + '\n')
        paths.append(rel + '.vmat')
    return paths


def owner_of(m, node, parent_of):
    """(entity index or None, classname, name) of the entity a mesh node sits under"""
    o = parent_of.get(node)
    while o is not None and o != m.world:
        if m.type(o) == b'CMapEntity': return o, m.cls(o), m.name(o)
        o = parent_of.get(o)
    return None, 'world', ''


def collect(m, specs):
    """{spec key: {owner key: {'ent': idx or None, 'faces': [(pts, uvs)]}}}; faces turned to nodraw"""
    parent_of = m.parent_of()
    out = {s['key']: {} for s in specs}
    n_faces = 0
    for node, _ in list(m.walk()):
        if m.type(node) != b'CMapMesh': continue
        md = m.g(node, b'meshData')
        if md is None or md < 0: continue
        mats_a = dmx.geta(m.E[md], b'materials')
        if mats_a is None: continue
        mats = [x.decode().lower() for x in mats_a[2]]
        hit = [i for i, x in enumerate(mats) if any(s['sub'] in x for s in specs)]
        if not hit: continue
        fd = m.g(md, b'faceData'); mis = stream(m, fd, b'materialindex')
        pos = stream(m, m.g(md, b'vertexData'), b'position'); tc = stream(m, m.g(md, b'faceVertexData'), b'texcoord')
        fei, evi, nxt, vdi, fdi, evd = (m.g(md, k) for k in (b'faceEdgeIndices', b'edgeVertexIndices', b'edgeNextIndices', b'vertexDataIndices',
                                                              b'faceDataIndices', b'edgeVertexDataIndices'))
        if None in (mis, pos, tc, fei, evi, nxt, vdi, fdi, evd): continue
        o = m.g(node, b'origin', [0, 0, 0]); ang = m.g(node, b'angles', [0, 0, 0]); sc = m.g(node, b'scales', [1, 1, 1])
        ent, cls, name = owner_of(m, node, parent_of)
        moving = cls in MOVERS or (cls == 'func_brush' and name)
        okey = ('%s:%s:%d' % (cls, name, ent)) if moving else 'static'
        for f, he in enumerate(fei):
            mi = mis[fdi[f]]
            if mi not in hit: continue
            spec = next(s for s in specs if s['sub'] in mats[mi])
            hs, h = [], he
            for _ in range(64):
                hs.append(h); h = nxt[h]
                if h == he: break
            pts = [V.xform([pos[vdi[evi[x]]][0] * sc[0], pos[vdi[evi[x]]][1] * sc[1], pos[vdi[evi[x]]][2] * sc[2]], o, ang) for x in hs]
            uvs = [(tc[evd[x]][0], tc[evd[x]][1]) for x in hs]
            g = out[spec['key']].setdefault(okey, {'ent': ent if moving else None, 'cls': cls, 'name': name, 'faces': []})
            g['faces'].append((pts, uvs))
            n_faces += 1
        for i in hit: mats_a[2][i] = NODRAW.encode()
    return out, n_faces


def newell(pts):
    nx = ny = nz = 0.0
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        nx += (a[1] - b[1]) * (a[2] + b[2]); ny += (a[2] - b[2]) * (a[0] + b[0]); nz += (a[0] - b[0]) * (a[1] + b[1])
    l = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return (nx / l, ny / l, nz / l)


VMDL = """<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc41:version{12fc9d44-453a-4ae4-b4d9-7e2ac0bbd4e0} -->
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


def _group(name, remaps):
    T = '\t'
    rm = "\n".join((T*7 + '{\n' + T*8 + 'from = "%s"\n' + T*8 + 'to = "%s"\n' + T*7 + '},') % r for r in remaps)
    if name is None:
        return (T*5 + '{\n' + T*6 + '_class = "DefaultMaterialGroup"\n' + T*6 + 'remaps =\n' + T*6 + '[\n%s\n' % rm + T*6 + ']\n'
                + T*6 + 'use_global_default = false\n' + T*6 + 'global_default_material = ""\n' + T*5 + '},')
    return (T*5 + '{\n' + T*6 + '_class = "MaterialGroup"\n' + T*6 + 'name = "%s"\n' % name + T*6 + 'remaps =\n' + T*6 + '[\n%s\n' % rm
            + T*6 + ']\n' + T*5 + '},')


def write_model(content, addon, key, idx, faces, origin, mat_paths):
    """SMD + vmdl (same writer as create/s2.py): ModelDoc turns SMD imports 90 degrees, so positions are written (y, -x, z)"""
    out = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0", "0 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000", "end", "triangles"]
    for pts, uvs in faces:
        n = newell(pts)
        rel = [(p[0] - origin[0], p[1] - origin[1], p[2] - origin[2]) for p in pts]
        for i in range(1, len(rel) - 1):
            out.append('f_00')
            for j in (0, i, i + 1):
                x, y, z = rel[j]; u, v = uvs[j]
                out.append("0 %.3f %.3f %.3f %.4f %.4f %.4f %.5f %.5f" % (y, -x, z, n[1], -n[0], n[2], u, -v))   # Hammer's V runs down, SMD's up
    out.append("end")
    name = '%s_%s_%d' % (addon, key, idx)
    d = os.path.join(content, 'models', 'port_anim'); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, name + '.smd'), 'w', newline='\n').write("\n".join(out) + "\n")
    groups = [_group(None, [('f_00.vmat', mat_paths[0])])] + [_group('f_%02d' % k, [(mat_paths[0], mat_paths[k])]) for k in range(1, len(mat_paths))]
    open(os.path.join(d, name + '.vmdl'), 'w', newline='\n').write(VMDL % ("\n".join(groups), name, 'models/port_anim/%s.smd' % name))
    return 'models/port_anim/%s.vmdl' % name


def centre(faces):
    xs = [p[i] for pts, _ in faces for p in pts for i in (0,)]; ys = [p[1] for pts, _ in faces for p in pts]; zs = [p[2] for pts, _ in faces for p in pts]
    return [round((min(xs) + max(xs)) / 2), round((min(ys) + max(ys)) / 2), round((min(zs) + max(zs)) / 2)]


JS = r'''
%s
// Flipbook textures on tiled faces (CS2's texture animation can't wrap inside a sheet cell): each is a prop_dynamic with one
// material group per frame; the think below steps Skin. Props on moving entities are glued on at round start (the entity may
// have moved to its first path_track at spawn, so the prop is placed at the owner's current origin first).
/** @type {{name: string, frames: number, fps: number, owner: string, ownerClass: string}[]} */
const PORT_ANIM = %s;
const portAnimSkin = PORT_ANIM.map(() => -1);
function portAnimAttach() {
    for (const a of PORT_ANIM) {
        if (!a.owner) continue;
        const prop = Instance.FindEntityByName(a.name); if (!prop) continue;
        const owners = Instance.FindEntitiesByName(a.owner).filter(e => !a.ownerClass || e.GetClassName() === a.ownerClass);
        let owner = owners[0];
        if (owners.length > 1 && a.spawn) {            // duplicate names: the one spawned where this prop's owner was expected
            let best = 1e18;
            for (const e of owners) {
                const o = e.GetAbsOrigin(); const d = (o.x - a.spawn[0]) ** 2 + (o.y - a.spawn[1]) ** 2 + (o.z - a.spawn[2]) ** 2;
                if (d < best) { best = d; owner = e; }
            }
        }
        if (!owner) continue;
        try {
            prop.SetParent(undefined);
            prop.Teleport({ position: owner.GetAbsOrigin(), angles: owner.GetAbsAngles() });
            prop.SetParent(owner);
        } catch (e) { Instance.Msg("port_anim: could not attach " + a.name + ": " + e); }
    }
}
Instance.OnRoundStart(() => { portAnimAttach(); for (let i = 0; i < portAnimSkin.length; i++) portAnimSkin[i] = -1; wakeThink(); });
THINKERS.push(() => {
    const t = Instance.GetGameTime();
    for (let i = 0; i < PORT_ANIM.length; i++) {
        const a = PORT_ANIM[i]; const f = Math.floor(t * a.fps) %% a.frames;
        if (f === portAnimSkin[i]) continue;
        portAnimSkin[i] = f;
        Instance.EntFireAtName({ name: a.name, input: "Skin", value: String(f) });
    }
    return true;
});
wakeThink();
%s
'''


def patch_script(js, table):
    import json
    block = JS % (MARK_A, json.dumps(table, indent=4), MARK_B)
    if MARK_A in js and MARK_B in js:
        return js[:js.index(MARK_A)] + block.strip('\n') + js[js.index(MARK_B) + len(MARK_B):]
    if 'const THINKERS' not in js:
        from gravity import THINK_JS
        js = js.rstrip('\n') + '\n\n' + THINK_JS
    return js.rstrip('\n') + '\n\n' + block.strip('\n') + '\n'


def run(m, content, addon, specs, log):
    groups, n_faces = collect(m, specs)
    table = []
    tracks = {m.name(e): m.origin(e) for e in m.by_class('path_track')}
    n_models = 0
    for spec in specs:
        mats = cut_frames(content, spec)
        for i, (okey, g) in enumerate(sorted(groups[spec['key']].items())):
            if g['ent'] is None: origin = centre(g['faces'])
            else: origin = m.origin(g['ent'])
            model = write_model(content, addon, spec['key'], i, g['faces'], origin, mats)
            tn = 'port_anim_%s_%d' % (spec['key'], i)
            m.new_entity('prop_dynamic', origin, {'targetname': tn, 'model': model, 'solid': '0', 'disableshadows': '1', 'skin': '0',
                                                   'rendertocubemaps': '0', 'lightingorigin': ''})
            row = {'name': tn, 'frames': spec['frames'], 'fps': spec['fps'], 'owner': g['name'] if g['ent'] is not None else '',
                   'ownerClass': g['cls'] if g['ent'] is not None else ''}
            if g['ent'] is not None and g['cls'] in ('func_tracktrain', 'func_tanktrain', 'func_train'):
                first = tracks.get(m.P(g['ent'], 'target', ''))
                if first: row['spawn'] = [round(x, 1) for x in first]
            table.append(row)
            n_models += 1
            log.append('%s: %d faces of %s -> %s (Skin 0..%d)%s' % (spec['key'], len(g['faces']), okey, model, spec['frames'] - 1,
                                                                   '' if g['ent'] is None else ', glued to %s %s at round start' % (g['cls'], g['name'] or '(unnamed)')))
    jp = os.path.join(content, 'maps', 'scripts', '%s_io.js' % addon)
    js = open(jp, encoding='utf-8').read() if os.path.exists(jp) else 'import { Instance } from "cs_script/point_script";\n'
    open(jp, 'w', encoding='utf-8', newline='\n').write(patch_script(js, table))
    script = '%s_io_script' % addon
    if not any(m.name(e) == script for e in m.by_class('point_script')):
        o = table and m.origin(next(e for e in m.entities() if m.name(e) == table[0]['name'])) or [0, 0, 0]
        m.new_entity('point_script', [o[0], o[1], o[2] + 64], {'targetname': script, 'cs_script': 'maps/scripts/%s_io.vjs' % addon})
        log.append('added point_script %s' % script)
    log.append('animprops: %d faces -> %d skinned props; originals now toolsnodraw' % (n_faces, n_models))
    return table


if __name__ == '__main__':
    if len(sys.argv) < 6: sys.exit(__doc__)
    vin, vout, content, addon = sys.argv[1:5]
    specs = [parse_spec(s) for s in sys.argv[5:]]
    mp = V.Map(vin); log = []
    run(mp, content, addon, specs, log)
    mp.save(vout)
    print('\n'.join(log))
