"""Prepare a rigged FBX (not a GMod item) for the pipeline: Blender export to <work>/fbx/<slug>/<slug>.npz (fbx_export.py), and a
Source-style material folder beside it so gmod2cs2 finds each material's textures the way it finds a GMod item's.

    python3 -I fbxprep.py <catalog.json> <slug>        (the pipeline calls prepare() for catalog items with "fbx")

Catalog item: {"slug", "fbx": "<path to .fbx>", "mtl": "<path to .mtl>" (default: the .fbx's name with .mtl), "id": 0,
"url": "<source page>", ...}. Textures come from the .mtl (map_Kd colour, map_Bump normal, map_d opacity: alpha-tested), the
form The Models Resource ships next to its FBX/OBJ rips. Materials: <root>/materials/fbx/<slug>/<material>.vmt + _c.png / _n.png.
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
    if not os.path.exists(npz) or os.path.getmtime(fbx) > os.path.getmtime(npz):
        log('   blender: exporting %s' % fbx)
        r = subprocess.run([blender(), '-b', '--factory-startup', '-P', os.path.join(HERE, 'fbx_export.py'), '--',
                            fbx.replace('\\', '/'), npz.replace('\\', '/')], capture_output=True, text=True, encoding='utf-8', errors='replace')
        for line in r.stdout.splitlines():
            if 'MISSING' in line or line.startswith('wrote'): log('   ' + line.strip())
        if not os.path.exists(npz): raise RuntimeError('fbx_export failed: %s' % (r.stderr or r.stdout)[-600:])
    mtl = read_mtl(it.get('mtl') or os.path.splitext(fbx)[0] + '.mtl')
    src_dir = os.path.dirname(fbx)
    md = os.path.join(root, 'materials', 'fbx', slug); os.makedirs(md, exist_ok=True)
    for m in np.load(npz)['materials']:
        m = str(m); b = safe(m); tx = mtl.get(m, {})
        vmt = os.path.join(md, b + '.vmt')
        if os.path.exists(vmt) and os.path.getmtime(vmt) > os.path.getmtime(npz): continue
        lines = ['"VertexLitGeneric"', '{']
        if tx.get('color'):
            im = Image.open(os.path.join(src_dir, tx['color'])).convert('RGBA')
            if tx.get('alpha'):
                a = Image.open(os.path.join(src_dir, tx['alpha'])).convert('L').resize(im.size)
                im.putalpha(a); lines.append('\t"$alphatest" "1"')
            else: im.putalpha(255)
            im.save(os.path.join(md, b + '_c.png')); lines.append('\t"$basetexture" "fbx/%s/%s_c"' % (slug, b))
        else: log('   ! %s: no colour texture in the .mtl' % m)
        if tx.get('normal') and os.path.exists(os.path.join(src_dir, tx['normal'])):
            Image.open(os.path.join(src_dir, tx['normal'])).convert('RGBA').save(os.path.join(md, b + '_n.png'))
            lines.append('\t"$bumpmap" "fbx/%s/%s_n"' % (slug, b))
        open(vmt, 'w', newline='\n').write('\n'.join(lines + ['}']) + '\n')
    return root, slug + '.npz'


if __name__ == '__main__':
    sys.path.insert(0, HERE)
    import fetch
    cat = json.load(open(sys.argv[1], encoding='utf-8'))
    it = next(i for i in cat['items'] if i.get('slug') == sys.argv[2])
    print(prepare(fetch.paths(cat)['work'], it))
