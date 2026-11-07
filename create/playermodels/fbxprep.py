"""Prepare a rigged FBX (not a GMod item) for the pipeline: Blender export to <work>/fbx/<slug>/<slug>.npz (fbx_export.py), and a
Source-style material folder beside it so gmod2cs2 finds each material's textures the way it finds a GMod item's.

    python3 -I fbxprep.py <catalog.json> <slug>        (the pipeline calls prepare() for catalog items with "fbx")

Catalog item: {"slug", "fbx": "<path to .fbx>", "mtl": "<path to .mtl>" (default: the .fbx's name with .mtl), "id": 0,
"url": "<source page>", ...}. Textures come from the .mtl (map_Kd colour, map_Bump normal, map_d opacity: alpha-tested), the
form The Models Resource ships next to its FBX/OBJ rips, else from the images fbx_export.py saved from the material nodes (GLB).
"fbx" may name a .glb. Materials: <root>/materials/fbx/<slug>/<material>.vmt + _c.png / _n.png.
Re-exported when the FBX is newer than the npz. Blender: env BLENDER, else the newest under Program Files/Blender Foundation.
"""
import glob, json, os, re, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def blender():
    b = os.environ.get('BLENDER')
    if b: return b
    c = sorted(glob.glob(r'C:\Program Files\Blender Foundation\Blender *\blender.exe'))
    if not c: raise RuntimeError('Blender not found (set BLENDER)')
    return c[-1]


def read_mtl(path):
    mats, cur = {}, None
    if not os.path.exists(path): return mats
    for line in open(path, encoding='utf-8', errors='replace'):
        w = line.strip().split(None, 1)
        if len(w) < 2: continue
        if w[0] == 'newmtl': cur = mats.setdefault(w[1].strip(), {})
        elif cur is not None and w[0] in ('map_Kd', 'map_Bump', 'map_bump', 'bump', 'map_d'):
            cur[{'map_Kd': 'color', 'map_d': 'alpha'}.get(w[0], 'normal')] = w[1].strip().split()[-1]
    return mats


def safe(n): return re.sub(r'[^A-Za-z0-9_]', '_', n).lower()


def prepare(work, it, log=print):
    """-> (root, mdl relative to root)"""
    from PIL import Image
    slug, fbx = it['slug'], it['fbx']
    root = os.path.join(work, 'fbx', slug); os.makedirs(root, exist_ok=True)
    npz = os.path.join(root, slug + '.npz')
    drop = ','.join(sorted(it.get('drop_materials', [])))     # "drop_materials": [names] leaves those materials out
    dropb = it.get('drop_bones', '')                            # "drop_bones": regex, parts skinned to those bones left out
    animp = bool(it.get('anim_pose'))                         # "anim_pose": true, rest pose from the file's first animation frame
    weap = bool(it.get('drop_weapons'))                       # "drop_weapons": true, weapons/props by bone and material name
    orph = bool(it.get('drop_orphans'))                       # "drop_orphans": true, props/weapons hung off the root left out
    foldb = it.get('fold_bones', '')
    foldd = it.get('fold_dir', 'backdown')                    # "fold_dir": down (capes) / back (a tail out behind) / backdown                            # "fold_bones": regex, chains swung back and down, kept rigid
    stale = not os.path.exists(npz) or max(os.path.getmtime(fbx), os.path.getmtime(os.path.join(HERE, 'fbx_export.py'))) > os.path.getmtime(npz)
    if not stale:
        z0 = np.load(npz); stale = (str(z0['drop']) if 'drop' in z0.files else '') != drop + ('|' + dropb if dropb else '') + ('^' + foldb + foldd if foldb else '') + ('~orphans' if orph else '') + ('~weapons' if weap else '') + ('~anim' if animp else '')
    if stale:
        log('   blender: exporting %s' % fbx)
        r = subprocess.run([blender(), '-b', '--factory-startup', '-P', os.path.join(HERE, 'fbx_export.py'), '--',
                            fbx.replace('\\', '/'), npz.replace('\\', '/')] + (['--drop', drop] if drop else []) + (['--drop-bones', dropb] if dropb else []) + (['--fold-bones', foldb, '--fold-dir', foldd] if foldb else []) + (['--drop-orphans'] if orph else []) + (['--drop-weapons'] if weap else []) + (['--anim-pose'] if animp else []), capture_output=True, text=True, encoding='utf-8', errors='replace')
        for line in r.stdout.splitlines():
            if 'MISSING' in line or 'folded' in line or 'rest pose' in line or 'left out' in line or line.startswith('wrote'): log('   ' + line.strip())
        if not os.path.exists(npz): raise RuntimeError('fbx_export failed: %s' % (r.stderr or r.stdout)[-600:])
    mtl = {m: {k: os.path.join(os.path.dirname(fbx), v) for k, v in tx.items()}
           for m, tx in read_mtl(it.get('mtl') or os.path.splitext(fbx)[0] + '.mtl').items()}
    z = np.load(npz)
    node_tex = json.loads(str(z['textures'])) if 'textures' in z.files else {}      # textures saved from the material nodes (GLB)
    md = os.path.join(root, 'materials', 'fbx', slug); os.makedirs(md, exist_ok=True)
    for m in z['materials']:
        m = str(m); b = safe(m)
        tx = mtl.get(m) or {k: os.path.join(root, v) for k, v in node_tex.get(m, {}).items()}
        vmt = os.path.join(md, b + '.vmt')
        if os.path.exists(vmt) and os.path.getmtime(vmt) > os.path.getmtime(npz): continue
        lines = ['"VertexLitGeneric"', '{']
        if tx.get('color'):
            im = Image.open(tx['color']).convert('RGBA')
            if tx.get('alpha'):
                a = Image.open(tx['alpha']).convert('L').resize(im.size)
                im.putalpha(a); lines.append('\t"$alphatest" "1"')
            else: im.putalpha(255)
            im.save(os.path.join(md, b + '_c.png')); lines.append('\t"$basetexture" "fbx/%s/%s_c"' % (slug, b))
        else: log('   ! %s: no colour texture in the .mtl' % m)
        if tx.get('normal') and os.path.exists(tx['normal']):
            Image.open(tx['normal']).convert('RGBA').save(os.path.join(md, b + '_n.png'))
            lines.append('\t"$bumpmap" "fbx/%s/%s_n"' % (slug, b))
        open(vmt, 'w', newline='\n').write('\n'.join(lines + ['}']) + '\n')
    return root, slug + '.npz'


if __name__ == '__main__':
    sys.path.insert(0, HERE)
    import fetch
    cat = json.load(open(sys.argv[1], encoding='utf-8'))
    it = next(i for i in cat['items'] if i.get('slug') == sys.argv[2])
    print(prepare(fetch.paths(cat)['work'], it))
