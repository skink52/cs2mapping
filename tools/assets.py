"""Missing material pass: every material the vmap uses must exist in the addon or in CS2's stock VPK.
Missing ones are rebuilt from CS:GO (VMT preloaded in csgo/pak01_dir.vpk, VTF from the archive chunks),
water-type materials are swapped for stock anubis/anubis_water_canal, anything with no source gets the closest stock CS2 material."""
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

COPY_RE = re.compile(r'^materials/maps/[^/]+/(.+?)((_wvt_patch)|(_-?\d+_-?\d+_-?\d+))+\.vmt$')


def compiler_copies(local):
    """{original 'materials/x.vmt': path of vbsp's full copy} for materials the map did not pack: vbsp writes copies next to the map
    (materials/maps/<map>/x_<x>_<y>_<z>.vmt for cubemaps, x_wvt_patch.vmt for a blend material on a brush face); when the map didn't
    pack x.vmt itself, a full copy is all that is left of it. Copies that only "patch" (include) another file are skipped; a
    _wvt_patch copy wins over a cubemap copy. From CS2-Porter bsp.py _recover_copy (MIT, copyright bcanusar), adapted: an index over
    the embedded files instead of extracted copies, used only after the map's own files and CS:GO's VPK."""
    out = {}
    for rel, p in sorted(local.items()):
        mm = COPY_RE.match(rel)
        if not mm: continue
        orig = 'materials/%s.vmt' % mm.group(1)
        if orig in local or (orig in out and '_wvt_patch' not in rel): continue
        try:
            with open(p, 'rb') as f: head = f.read(256).lstrip(b'\xef\xbb\xbf \t\r\n').lower()
        except OSError: continue
        if not head or head.startswith(b'patch') or head.startswith(b'"patch"'): continue
        out[orig] = p
    return out


class Source:
    """CS:GO files: the map's own embedded files first (BSPSource output), then csgo/pak01 VPK, then vbsp's full copies of materials
    the map didn't pack (compiler_copies; s.copies_used lists the ones read)."""
    def __init__(s, c, csgo_vpk, archives):
        s.c = c; s.vpk = csgo_vpk; s.arcs = archives; s.local = {}
        emb = os.path.join(c.root, 'embedded', c.addon)
        for dp, _, fs in os.walk(emb):
            for f in fs:
                p = os.path.join(dp, f); s.local[os.path.relpath(p, emb).replace(os.sep, '/').lower()] = p
        s.copies = compiler_copies(s.local); s.copies_used = {}
    def has(s, path): path = path.lower(); return path in s.local or s.vpk.has(path) or path in s.copies
    def read(s, path):
        """bytes, or None when a VPK chunk must be staged first (added to c.need)"""
        path = path.lower()
        if path in s.local: return open(s.local[path], 'rb').read()
        if not s.vpk.has(path) and path in s.copies:
            s.copies_used[path] = os.path.basename(s.copies[path])
            with open(s.copies[path], 'rb') as f: return f.read()
        if not s.vpk.has(path): return None
        arc = s.vpk.archive_of(path)
        if arc != 0x7fff and arc not in s.arcs and s.vpk.files[path][2] > 0:
            s.c.need.add(arc); getattr(s.c, 'need_paths', set()).add(path); return None
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

INVERTED_NORMAL_TXT = '"settings"\n{\n\t"legacy_source1_inverted_normal"\t\t"1"\n}\n'


def _tex_name(v):
    v = (v or '').strip().lower().replace('\\', '/')
    return v[:-4] if v.endswith('.vtf') else v


def convert_texture(c, src, name, normal=False, ssbump=False):
    """CS:GO texture materials/<name>.vtf -> addon image. Colour / mask: <name>.png. Normal: <name>_normal.tga plus the
    legacy_source1_inverted_normal sidecar .txt, as Valve's importer writes it (keimusho flagstone_d_normals_normal.tga: same pixels as the
    VTF, the sidecar flips green at compile); $ssbump maps rebuilt as real normals first (texfix.ssbump_to_normal), <name>_ssbn.tga.
    Returns the content-relative path, '' when CS:GO has no such texture, None when a VPK chunk must be staged first."""
    name = _tex_name(name)
    if not name: return ''
    rel = 'materials/' + name + (('_ssbn.tga' if ssbump else '_normal.tga') if normal else '.png')
    if c.exists(rel): return rel
    vtfp = 'materials/' + name + '.vtf'
    if not src.has(vtfp): return ''
    data = src.read(vtfp)
    if data is None: return None
    img = vtf.decode(data); b = io.BytesIO()
    if normal:
        img = img.convert('RGB')
        if ssbump:
            try:
                import texfix
                img = texfix.ssbump_to_normal(img)
            except ImportError: pass               # no numpy: the radiosity values go through as they are (as the importer does)
        img.save(b, 'TGA'); c.write(rel, b.getvalue()); c.write(rel[:-4] + '.txt', INVERTED_NORMAL_TXT)
    else:
        img.convert('RGBA' if vtf.has_alpha(img) else 'RGB').save(b, 'PNG'); c.write(rel, b.getvalue())
    return rel


def blend_vmat(src_desc, kv, col1, col2, nrm1='', nrm2='', mod=''):
    """Two-layer csgo_lightmappedgeneric vmat for a CS:GO WorldVertexTransition material, in the form Valve's importer writes
    (keimusho brick_g1_blend.vmat, mg_nature_multigames blendmilground004_2.vmat): F_LAYERS 1, F_FANCY_BLENDING 1 only with
    $blendmodulatetexture, a TextureLayerNNormal only when the vmt has that $bumpmap."""
    q = lambda k, v: '\t"%s"\t\t"%s"\n' % (k, v)
    s = '// Rebuilt from CS:GO %s (WorldVertexTransition: %s + %s).\n"Layer0"\n{\n' % (src_desc, _tex_name(kv.get('$basetexture')), _tex_name(kv.get('$basetexture2')))
    s += q('Shader', 'csgo_lightmappedgeneric.vfx')
    for n, colr, nrm in ((1, col1, nrm1), (2, col2, nrm2)):
        s += q('TextureLayer%dColor' % n, colr)
        if nrm: s += q('TextureLayer%dNormal' % n, nrm)
        s += q('TextureLayer%dRoughness' % n, 'materials/default/default_rough_s1import.tga')
        s += q('TextureLayer%dAmbientOcclusion' % n, 'materials/default/default_ao.tga')
    if mod: s += q('TextureBlendModulation', mod)
    s += q('F_LAYERS', '1') + q('g_vLayer1Tint', '[1.000000 1.000000 1.000000]') + q('g_vLayer2Tint', '[1.000000 1.000000 1.000000]')
    s += q('F_FANCY_BLENDING', '1' if mod else '0') + q('F_TEXTURETRANSFORMS', '0')
    sp = [(k, kv[k2]) for k, k2 in (('PhysicsSurfaceProperties', '$surfaceprop'), ('PhysicsSurfaceProperties2', '$surfaceprop2')) if kv.get(k2)]
    if sp: s += '\t"SystemAttributes"\n\t{\n' + ''.join('\t' + q(k, v) for k, v in sp) + '\t}\n'
    return s + '}\n'


def write_blend(c, src, mat, vmt, kv):
    """WorldVertexTransition with $basetexture2 -> two-layer vmat. True when written, None when a VPK chunk must be staged first,
    False when the first layer's texture is missing (the caller goes on as for a one-layer material)."""
    ssb = kv.get('$ssbump') == '1'
    got = {}
    for key, normal in (('$basetexture', False), ('$basetexture2', False), ('$bumpmap', True), ('$bumpmap2', True), ('$blendmodulatetexture', False)):
        if not kv.get(key): got[key] = ''; continue
        r = convert_texture(c, src, kv[key], normal, ssb and normal)
        if r is None: return None
        got[key] = r
    if not got['$basetexture']: return False
    col2 = got['$basetexture2'] or got['$basetexture']   # second layer missing: both layers the first texture (paint does nothing, but no error)
    c.write(mat, blend_vmat(vmt, kv, got['$basetexture'], col2, got['$bumpmap'], got['$bumpmap2'], got['$blendmodulatetexture']))
    return True


def fix_materials(m, c, cs2_vpk, csgo_vpk, csgo_archives):
    """csgo_archives: {index: local path} of staged CS:GO pak01_NNN.vpk chunks. Adds to c.need what must be staged."""
    src = Source(c, csgo_vpk, csgo_archives)
    stock = set(k[:-2] for k in cs2_vpk.files if k.endswith('.vmat_c'))
    stock_by_dir = collections.defaultdict(list)
    for s in stock: stock_by_dir[os.path.dirname(s)].append(s)
    used = mesh_materials(m)
    stubs = stub_materials(c)
    rebuilt, swapped, substituted, stuck, blends = [], [], [], [], []
    WATER = 'materials/anubis/anubis_water_canal.vmat'   # skink52's default since 2 Nov 2026 (was liquids/nuke_water)
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
            if shader == 'worldvertextransition' and kv.get('$basetexture2'):
                r = write_blend(c, src, mat, vmt, kv)
                if r is None: continue                        # waiting on a VPK chunk
                if r: blends.append(os.path.basename(mat)[:-5] + (' (over a CS2 stub)' if mat in stubs else '')); continue
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
    if blends: c.log.append('built %d missing blend (WorldVertexTransition) materials as two-layer csgo_lightmappedgeneric, as the importer '
                            'writes them (paint them with blendpaint / Hammer\'s Paint Blend): %s' % (len(blends), ', '.join(blends)))
    if src.copies_used:
        c.log.append('materials the map did not pack, read from the compiler\'s copies in the BSP: %s'
                     % ', '.join('%s (%s)' % (k[len('materials/'):-4], v) for k, v in sorted(src.copies_used.items())))
        wvt = [k[len('materials/'):-4] for k, v in sorted(src.copies_used.items()) if '_wvt_patch' in v.lower()]
        if wvt: c.todo.append('materials rebuilt from vbsp\'s _wvt_patch copy (the brush-face version of a blend material; a displacement using it '
                              'shows one layer): %s' % ', '.join(wvt))
    if swapped: c.log.append('CS:GO water materials (no CS2 equivalent shader) -> stock: %s' % '; '.join(swapped))
    if substituted: c.log.append('materials missing everywhere swapped for the closest stock CS2 ones: %s' % '; '.join(substituted))
    if substituted: c.todo.append('check the substituted materials look right: %s' % '; '.join(substituted))
    if stuck: c.todo.append('materials still missing: %s' % '; '.join(stuck))

def upgrade_blends(m, c, csgo_vpk, csgo_archives, src=None):
    """Opt-in: blend materials an earlier `assets` run rebuilt as one csgo_complex layer (header '// Rebuilt from CS:GO', no F_LAYERS)
    whose CS:GO vmt is WorldVertexTransition with $basetexture2 -> rewritten as two-layer vmats (write_blend). Only those headers are
    touched, so importer-written and hand-made vmats are never changed. Returns the rewritten material paths."""
    src = src or Source(c, csgo_vpk, csgo_archives)
    done = []
    for mat in sorted(mesh_materials(m)):
        if not mat.endswith('.vmat') or mat.startswith('materials/tools/'): continue
        if mat in c.files: txt = c.files[mat].decode('utf-8', 'replace')
        else:
            p = os.path.join(c.content, mat)
            if not os.path.exists(p): continue
            with open(p, encoding='utf-8', errors='replace') as fh: txt = fh.read()
        if not txt.startswith('// Rebuilt from CS:GO') or re.search(r'F_LAYERS"?\s+"?[1-9]', txt): continue
        vmt = mat[:-5] + '.vmt'
        if not src.has(vmt): continue
        shader, kv = load_vmt(src, vmt)
        if shader != 'worldvertextransition' or not kv.get('$basetexture') or not kv.get('$basetexture2'): continue
        if write_blend(c, src, mat, vmt, kv): done.append(mat)
    if done: c.log.append('one-layer blend materials rewritten as two-layer csgo_lightmappedgeneric: %s' % ', '.join(os.path.basename(x)[:-5] for x in done))
    return done


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
    """imported materials whose CS:GO original was $alphatest / $translucent but came through opaque (no flag, or a flag with no mask)"""
    from PIL import Image
    done = []
    for mat in sorted(mesh_materials(m)):
        vp = os.path.join(c.content, mat)
        if not os.path.exists(vp) or c.src is None: continue
        txt = c.files.get(mat, b'').decode() or open(vp, encoding='utf-8', errors='replace').read()
        # skip materials that already have a mask; F_TRANSLUCENT / F_ALPHA_TEST with no TextureTranslucency still draws opaque on
        # csgo_complex (the colour alpha isn't used - mg_yolo_multigames banners, 29 Oct 2026), so those are fixed too
        if 'TextureTranslucency' in txt or 'csgo_complex' not in txt: continue
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


def main(argv=None):
    """python assets.py upgrade-blends <map.vmap> <addon content dir> <out dir> [--root <stage root>] [--csgo <CS:GO csgo folder>]
    Writes the two-layer vmats and their textures under <out dir> (content-relative paths) for review; it never writes into the addon."""
    import argparse, glob, sys
    import vmapedit as V
    ap = argparse.ArgumentParser(description='rewrite one-layer rebuilt blend vmats as two-layer (writes to <out>, not the addon)')
    ap.add_argument('cmd', choices=['upgrade-blends']); ap.add_argument('vmap'); ap.add_argument('content'); ap.add_argument('out')
    ap.add_argument('--root', help='stage root holding vpk/csgo_pak01_dir.vpk and embedded/<addon> (default: the CS:GO install via --csgo)')
    ap.add_argument('--csgo', help='CS:GO csgo folder (pak01_dir.vpk + pak01_NNN.vpk), read only')
    a = ap.parse_args(argv)
    content = os.path.abspath(a.content); out = os.path.abspath(a.out)
    if os.path.normcase(out).startswith(os.path.normcase(content)): ap.error('<out> must not be inside the addon')
    class C: pass
    c = C(); c.addon = os.path.basename(content.rstrip('/\\')); c.root = os.path.abspath(a.root or out); c.content = content
    c.log = []; c.todo = []; c.files = {}; c.need = set(); c.need_paths = set()
    c.write = lambda rel, d: c.files.__setitem__(rel, d if isinstance(d, bytes) else d.encode('utf-8'))
    c.exists = lambda rel: rel.lower() in c.files or os.path.exists(os.path.join(content, rel))
    if a.csgo:
        v = vpk.VPK(os.path.join(a.csgo, 'pak01_dir.vpk'))
        arcs = {int(p[-7:-4]): p for p in glob.glob(os.path.join(a.csgo, 'pak01_[0-9][0-9][0-9].vpk'))}
    else:
        vd = os.path.join(c.root, 'vpk'); v = vpk.VPK(os.path.join(vd, 'csgo_pak01_dir.vpk'))
        arcs = {int(f[11:14]): os.path.join(vd, f) for f in os.listdir(vd) if re.match(r'csgo_pak01_\d{3}\.vpk$', f)}
    m = V.Map(a.vmap)
    done = upgrade_blends(m, c, v, arcs)
    for rel, data in sorted(c.files.items()):
        p = os.path.join(out, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as fh: fh.write(data)
    for l in c.log + ['TO CHECK: ' + t for t in c.todo]: print(l)
    if c.need: print('VPK chunks to stage first: %s' % sorted(c.need))
    print('%d blend vmats, %d files written under %s' % (len(done), len(c.files), out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
