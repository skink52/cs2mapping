"""Missing material pass: every material the vmap uses must exist in the addon or in CS2's stock VPK.
Missing ones are rebuilt from CS:GO (VMT preloaded in csgo/pak01_dir.vpk, VTF from the archive chunks),
water-type materials are swapped for stock liquids/nuke_water, anything with no source gets the closest stock CS2 material."""
import os, re, io, difflib, collections
import dmx, vpk, vtf

VMAT = '''// Rebuilt from CS:GO %(src)s (basetexture %(base)s).
Layer0
{
    shader "%(shader)s"
%(extra)s
    //---- Material ----
    TextureColor "%(col)s"
%(trans)s
    //---- Normal ----
    TextureNormal "materials\\default\\default_normal.tga"

    //---- Roughness ----
    TextureRoughness "materials\\default\\default_rough.tga"

    //---- Metalness ----
    TextureMetalness "materials\\default\\default_metal.tga"
}
'''

def parse_vmt(txt):
    txt = re.sub(r'//[^\n]*', '', txt)
    m = re.match(r'\s*"?([A-Za-z0-9_]+)"?', txt)
    shader = m.group(1).lower() if m else ''
    kv = {}
    for k, v in re.findall(r'"?(\$[A-Za-z0-9_]+|include)"?\s+"?([^"\n{}]*?)"?\s*(?:\n|$)', txt):
        kv.setdefault(k.lower(), v.strip())
    return shader, kv

def mesh_materials(m):
    use = collections.defaultdict(list)
    for i, e in enumerate(m.E):
        if e['type'] == b'CDmePolygonMesh':
            for x in dmx.get(e, b'materials') or []: use[x.decode().lower().replace('\\', '/')].append(i)
    return use

def replace_material(m, old, new):
    n = 0
    for e in m.E:
        if e['type'] == b'CDmePolygonMesh':
            a = dmx.geta(e, b'materials')
            if a and any(x.decode().lower() == old for x in a[2]):
                a[2] = [new.encode() if x.decode().lower() == old else x for x in a[2]]; n += 1
    return n

class Source:
    """CS:GO files: the map's own embedded files first (BSPSource output), then csgo/pak01 VPK."""
    def __init__(s, c, csgo_vpk, archives):
        s.c = c; s.vpk = csgo_vpk; s.arcs = archives; s.local = {}
        emb = os.path.join(c.root, 'embedded', c.addon)
        for dp, _, fs in os.walk(emb):
            for f in fs:
                p = os.path.join(dp, f); s.local[os.path.relpath(p, emb).replace(os.sep, '/').lower()] = p
    def has(s, path): path = path.lower(); return path in s.local or s.vpk.has(path)
    def read(s, path):
        """bytes, or None when a VPK chunk must be staged first (added to c.need)"""
        path = path.lower()
        if path in s.local: return open(s.local[path], 'rb').read()
        if not s.vpk.has(path): return None
        arc = s.vpk.archive_of(path)
        if arc != 0x7fff and arc not in s.arcs and s.vpk.files[path][2] > 0:
            s.c.need.add(arc); return None
        return s.vpk.read(path, s.arcs)

def load_vmt(src, vmt):
    raw = src.read(vmt)
    if raw is None: return None, None
    shader, kv = parse_vmt(raw.decode('utf-8', 'replace'))
    if shader == 'patch' and kv.get('include'):
        inc = kv['include'].lower().replace('\\', '/')
        r2 = src.read(inc)
        if r2 is not None:
            s2, kv2 = parse_vmt(r2.decode('utf-8', 'replace')); shader = s2; kv = {**kv2, **kv}
    return shader, kv

def write_vmat(c, mat, src_desc, base, col, img, kv):
    alpha = img is not None and vtf.has_alpha(img) and (kv.get('$translucent') == '1' or kv.get('$alphatest') == '1')
    trans = extra = ''
    if alpha:
        mk = 'materials/' + base + '_trans.png'; b = io.BytesIO(); img.getchannel('A').save(b, 'PNG'); c.write(mk, b.getvalue())
        extra = '    F_ALPHA_TEST 1\n' if kv.get('$alphatest') == '1' else '    F_TRANSLUCENT 1\n'
        trans = '\n    //---- Translucent ----\n    TextureTranslucency "%s"\n' % mk.replace('/', '\\')
    c.write(mat, VMAT % dict(src=src_desc, base=base, shader='csgo_complex.vfx', col=col.replace('/', '\\'), trans=trans, extra=extra))
    return alpha

def fix_materials(m, c, cs2_vpk, csgo_vpk, csgo_archives):
    """csgo_archives: {index: local path} of staged CS:GO pak01_NNN.vpk chunks. Adds to c.need what must be staged."""
    src = Source(c, csgo_vpk, csgo_archives)
    stock = set(k[:-2] for k in cs2_vpk.files if k.endswith('.vmat_c'))
    stock_by_dir = collections.defaultdict(list)
    for s in stock: stock_by_dir[os.path.dirname(s)].append(s)
    used = mesh_materials(m)
    stubs = stub_materials(c)
    rebuilt, swapped, substituted, stuck = [], [], [], []
    WATER = 'materials/liquids/nuke_water.vmat'
    for mat in sorted(used):
        if not mat.endswith('.vmat') or mat.startswith('materials/tools/'): continue
        if (mat in stock and mat not in stubs) or c.exists(mat): continue
        vmt = mat[:-5] + '.vmt'
        shader, kv = load_vmt(src, vmt) if src.has(vmt) else (None, None)
        if mat in stubs and shader is None and not src.has(vmt):
            stuck.append(mat + ' (stock CS2 stub - draws the error material - and no CS:GO source to re-port it from)'); continue
        if shader is None and src.has(vmt): continue          # waiting on a VPK chunk
        if shader is not None:
            if shader == 'water' or (not kv.get('$basetexture') and 'water' in mat):
                replace_material(m, mat, WATER); swapped.append('%s -> %s' % (mat, WATER)); continue
            if not kv.get('$basetexture'):
                stuck.append(mat + ' (CS:GO %s material has no $basetexture)' % shader); continue
            base = kv['$basetexture'].lower().replace('\\', '/')
            if base.endswith('.vtf'): base = base[:-4]
        else:
            kv = {}; base = mat[len('materials/'):-5]
        col = 'materials/' + base + '.png'
        if c.exists(col):                                    # texture already converted into the addon
            img = None
            if (kv.get('$translucent') == '1' or kv.get('$alphatest') == '1') and src.has('materials/' + base + '.vtf'):
                data = src.read('materials/' + base + '.vtf')   # the addon png may have lost its alpha: take it from the CS:GO texture
                if data is None: continue
                img = vtf.decode(data)
            write_vmat(c, mat, vmt, base, col, img, kv); rebuilt.append(os.path.basename(mat)[:-5]); continue
        vtfp = 'materials/' + base + '.vtf'
        if src.has(vtfp):
            data = src.read(vtfp)
            if data is None: continue                         # waiting on a VPK chunk
            img = vtf.decode(data)
            b = io.BytesIO(); img.convert('RGBA' if vtf.has_alpha(img) else 'RGB').save(b, 'PNG'); c.write(col, b.getvalue())
            alpha = write_vmat(c, mat, vmt, base, col, img, kv)
            rebuilt.append(os.path.basename(mat)[:-5] + (' (alpha)' if alpha else '') + (' (over a CS2 stub)' if mat in stubs else '')); continue
        if 'water' in mat:
            replace_material(m, mat, WATER); swapped.append('%s -> %s' % (mat, WATER)); continue
        d = os.path.dirname(mat); nm = os.path.basename(mat)
        if mat.startswith('materials/decals/'):
            stuck.append(mat + ' (custom decal with no CS:GO source - left as is rather than swapped for an unrelated decal)'); continue
        pool = stock_by_dir.get(d) or []
        best = difflib.get_close_matches(mat, pool, 1, 0.5) or difflib.get_close_matches(nm, [os.path.basename(p) for p in stock if not p.startswith('stickers/')], 1, 0.75)
        if best:
            new = best[0] if '/' in best[0] else next(p for p in stock if os.path.basename(p) == best[0])
            if 'decal' in mat and 'decal' not in new:
                stuck.append(mat + ' (decal with no CS:GO source; closest stock match %s is not a decal, so left as is)' % new); continue
            replace_material(m, mat, new); substituted.append('%s -> %s' % (mat, new))
        else:
            stuck.append(mat + ' (no CS:GO source and no similar stock CS2 material)')
    if rebuilt: c.log.append('built %d missing materials from the original CS:GO textures: %s' % (len(rebuilt), ', '.join(rebuilt)))
    if swapped: c.log.append('CS:GO water materials (no CS2 equivalent shader) -> stock: %s' % '; '.join(swapped))
    if substituted: c.log.append('materials missing everywhere swapped for the closest stock CS2 ones: %s' % '; '.join(substituted))
    if substituted: c.todo.append('check the substituted materials look right: %s' % '; '.join(substituted))
    if stuck: c.todo.append('materials still missing: %s' % '; '.join(stuck))

def stub_materials(c):
    """stock CS2 materials Valve shipped as stubs (error shader), from maps/<addon>_stub_materials.txt written on the PC by vmap_refs.py"""
    rel = 'maps/%s_stub_materials.txt' % c.addon
    p = os.path.join(c.content, rel)
    if not os.path.exists(p):
        c.todo.append('%s not staged (vmap_refs.py on the PC writes it during stage B): stock CS2 materials that are error-shader stubs were not checked' % rel)
        return set()
    return set(l.split('\t')[0].strip().lower() for l in open(p, encoding='utf-8', errors='replace') if l.strip() and not l.startswith('//'))

def check_models(m, c, cs2_vpk):
    missing = collections.Counter()
    for e in m.entities():
        mdl = (m.P(e, 'model') or '').lower().replace('\\', '/')
        if not mdl.endswith('.vmdl'): continue
        if cs2_vpk.has(mdl + '_c') or c.exists(mdl): continue
        missing[mdl] += 1
    if missing: c.todo.append('models referenced but not in the addon or CS2: %s' % ', '.join('%s x%d' % kv for kv in missing.most_common())[:800])


def fix_alpha(m, c):
    """imported materials whose CS:GO original was $alphatest / $translucent but came through opaque"""
    from PIL import Image
    done = []
    for mat in sorted(mesh_materials(m)):
        vp = os.path.join(c.content, mat)
        if not os.path.exists(vp) or c.src is None: continue
        txt = c.files.get(mat, b'').decode() or open(vp, encoding='utf-8', errors='replace').read()
        if 'F_ALPHA_TEST' in txt or 'F_TRANSLUCENT' in txt or 'csgo_complex' not in txt: continue
        shader, kv = load_vmt(c.src, mat[:-5] + '.vmt') if c.src.has(mat[:-5] + '.vmt') else (None, None)
        if not kv or not (kv.get('$alphatest') == '1' or kv.get('$translucent') == '1'): continue
        mc = re.search(r'TextureColor"?\s+"([^"]+)"', txt)
        if not mc: continue
        col = mc.group(1).replace('\\', '/'); cp = os.path.join(c.content, col)
        img = Image.open(cp) if os.path.exists(cp) else None
        if img is None or 'A' not in img.getbands() or img.getchannel('A').getextrema()[0] == 255:
            # the png came through without alpha (or isn't staged): take the alpha from the CS:GO texture itself
            vb = (kv.get('$basetexture') or '').lower().replace('\\', '/')
            vb = vb[:-4] if vb.endswith('.vtf') else vb
            data = c.src.read('materials/' + vb + '.vtf') if vb and c.src.has('materials/' + vb + '.vtf') else None
            img = vtf.decode(data) if data else None
        if img is None or 'A' not in img.getbands() or img.getchannel('A').getextrema()[0] == 255: continue
        base = os.path.splitext(col)[0][len('materials/'):]
        write_vmat(c, mat, mat[:-5] + '.vmt', base, col, img.convert('RGBA'), kv)
        done.append(os.path.basename(mat)[:-5] + (' (alpha test)' if kv.get('$alphatest') == '1' else ' (translucent)'))
    if done: c.log.append('%d materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: %s' % (len(done), ', '.join(done)))
