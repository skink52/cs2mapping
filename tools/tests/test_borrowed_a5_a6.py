"""A5 assets.compiler_copies / Source (materials the map didn't pack, from vbsp's copies in the pakfile) and A6 texfix.face_scales on
faces the importer scaled for an 8192-wide texture (material missing at import).

  python -m unittest discover -s tools/tests -p "test_borrowed_a5_a6.py" -v
"""
import os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import assets, texfix, vmapedit as V, watervol, dmx


class FakeVPK:
    def __init__(s, files): s.files = {k: (0x7fff, 0, len(v), b'') for k, v in files.items()}; s.data = files
    def has(s, p): return p.lower() in s.files
    def archive_of(s, p): return 0x7fff
    def read(s, p, arcs): return s.data[p.lower()]


class Ctx:
    def __init__(s, root, addon='zz_test'):
        s.root = root; s.addon = addon; s.content = os.path.join(root, 'content', addon)
        s.files = {}; s.log = []; s.todo = []; s.need = set(); s.src = None; s.pc_files = set()
    def write(s, rel, data): s.files[rel] = data if isinstance(data, bytes) else data.encode('utf-8')
    def exists(s, rel): return rel in s.files or os.path.exists(os.path.join(s.content, rel))


class CompilerCopies(unittest.TestCase):
    def setUp(s):
        s.tmp = tempfile.mkdtemp(prefix='borrowed_a5_')
        s.emb = os.path.join(s.tmp, 'embedded', 'zz_test')
        def put(rel, txt):
            p = os.path.join(s.emb, *rel.split('/')); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w').write(txt)
        put('materials/maps/zz_test/custom/blend_wvt_patch.vmt', 'LightmappedGeneric\n{\n"$basetexture" "custom/grass"\n}\n')
        put('materials/maps/zz_test/custom/blend_10_-20_30.vmt', 'LightmappedGeneric\n{\n"$basetexture" "custom/cubemapcopy"\n}\n')
        put('materials/maps/zz_test/custom/panel_1_2_3.vmt', 'patch\n{\n"include" "materials/custom/panel.vmt"\n}\n')
        put('materials/maps/zz_test/custom/packed_1_2_3.vmt', 'LightmappedGeneric\n{\n"$basetexture" "custom/x"\n}\n')
        put('materials/custom/packed.vmt', 'LightmappedGeneric\n{\n"$basetexture" "custom/packed"\n}\n')
        put('materials/maps/zz_test/stock/wall_1_2_3.vmt', 'LightmappedGeneric\n{\n"$basetexture" "stock/fromcopy"\n}\n')

    def tearDown(s): shutil.rmtree(s.tmp, ignore_errors=True)

    def test_index(s):
        local = {}
        for dp, _, fs in os.walk(s.emb):
            for f in fs: p = os.path.join(dp, f); local[os.path.relpath(p, s.emb).replace(os.sep, '/').lower()] = p
        cp = assets.compiler_copies(local)
        s.assertEqual(sorted(cp), ['materials/custom/blend.vmt', 'materials/stock/wall.vmt'])     # patch and packed ones skipped
        s.assertTrue(cp['materials/custom/blend.vmt'].endswith('blend_wvt_patch.vmt'))             # wvt copy wins over the cubemap copy

    def test_source_order(s):
        c = Ctx(s.tmp)
        src = assets.Source(c, FakeVPK({'materials/stock/wall.vmt': b'LightmappedGeneric\n{\n"$basetexture" "stock/fromvpk"\n}\n'}), {})
        s.assertTrue(src.has('materials/custom/blend.vmt'))
        s.assertEqual(assets.load_vmt(src, 'materials/custom/blend.vmt')[1]['$basetexture'], 'custom/grass')
        s.assertEqual(assets.load_vmt(src, 'materials/stock/wall.vmt')[1]['$basetexture'], 'stock/fromvpk')    # VPK before the copy
        s.assertEqual(list(src.copies_used), ['materials/custom/blend.vmt'])
        s.assertFalse(src.has('materials/custom/panel.vmt'))


def face_loops(m, node):
    """[(face data index, [(vertex position, texcoord index)])] of a mesh"""
    md = m.g(node, b'meshData')
    fei, evi, nxt, vdi, evd, fdi = (m.g(md, k) for k in (b'faceEdgeIndices', b'edgeVertexIndices', b'edgeNextIndices', b'vertexDataIndices',
                                                          b'edgeVertexDataIndices', b'faceDataIndices'))
    pos = texfix.stream(m, m.g(md, b'vertexData'), b'position')
    out = []
    for f, he in enumerate(fei):
        hs, h = [], he
        while True:
            hs.append(h); h = nxt[h]
            if h == he: break
        out.append((fdi[f] if fdi else f, [(pos[vdi[evi[x]]], evd[x]) for x in hs]))
    return out


class PlaceholderScale(unittest.TestCase):
    def setUp(s):
        s.tmp = tempfile.mkdtemp(prefix='borrowed_a6_')
        s.c = Ctx(s.tmp)
        os.makedirs(os.path.join(s.c.content, 'materials', 'test'))
        open(os.path.join(s.c.content, 'materials', 'test', 'wall.vmat'), 'w').write('Layer0\n{\n\tshader "csgo_complex.vfx"\n\tTextureColor "materials\\test\\wall.png"\n}\n')
        from PIL import Image
        Image.new('RGB', (512, 256)).save(os.path.join(s.c.content, 'materials', 'test', 'wall.png'))
        s.m = V.Map(watervol.TEMPLATE)
        tm = V.Map(watervol.TEMPLATE); tnode = tm.children(tm.world)[0]
        s.node = watervol.box(s.m, tm, tnode, [0, 0, 0], [256, 128, 64], b'materials/test/wall.vmat')
        dmx.geta(s.m.E[s.m.world], b'children')[2].append(s.node)
        md = s.m.g(s.node, b'meshData'); fd = s.m.g(md, b'faceData')
        s.sc, s.u, s.v = (texfix.stream(s.m, fd, k) for k in (b'texturescale', b'textureaxisu', b'textureaxisv'))
        s.tc = texfix.stream(s.m, s.m.g(md, b'faceVertexData'), b'texcoord')
        for fi, loop in face_loops(s.m, s.node):          # what the importer writes for a material it couldn't find: 0.25 for 8192
            s.sc[fi] = [0.25 * 512 / 8192, 0.25 * 256 / 8192]; s.u[fi] = s.u[fi][:3] + [16.0]; s.v[fi] = s.v[fi][:3] + [8.0]
            for P, ti in loop:
                s.tc[ti] = [(texfix.dot(P, s.u[fi]) / s.sc[fi][0] + s.u[fi][3]) / 8192.0, (texfix.dot(P, s.v[fi]) / s.sc[fi][1] + s.v[fi][3]) / 8192.0]
        s.before = [list(t) for t in s.tc]

    def tearDown(s): shutil.rmtree(s.tmp, ignore_errors=True)

    def test_implied_widths(s):
        fi, loop = face_loops(s.m, s.node)[0]
        w = texfix.implied_widths(loop, s.tc, s.u[fi], s.v[fi], s.sc[fi])
        s.assertAlmostEqual(w[0], 8192.0, places=2); s.assertAlmostEqual(w[1], 8192.0, places=2)

    def test_rescaled_without_vmf(s):
        texfix.face_scales(s.m, s.c, os.path.join(s.tmp, 'none.vmf'))
        for fi, loop in face_loops(s.m, s.node):
            s.assertAlmostEqual(s.sc[fi][0], 0.25, places=6); s.assertAlmostEqual(s.sc[fi][1], 0.25, places=6)
            s.assertAlmostEqual(s.u[fi][3], 1.0, places=6); s.assertAlmostEqual(s.v[fi][3], 0.25, places=6)
            w = texfix.implied_widths(loop, s.tc, s.u[fi], s.v[fi], s.sc[fi])
            s.assertAlmostEqual(w[0], 512.0, places=2); s.assertAlmostEqual(w[1], 256.0, places=2)
        for a, b in zip(s.before, s.tc):                  # the look is unchanged
            s.assertAlmostEqual(a[0], b[0], places=9); s.assertAlmostEqual(a[1], b[1], places=9)
        s.assertTrue(any('8192-wide' in x for x in s.c.log))

    def test_right_scale_untouched(s):
        for fi, loop in face_loops(s.m, s.node):
            s.sc[fi] = [0.25, 0.25]
            for P, ti in loop:
                s.tc[ti] = [(texfix.dot(P, s.u[fi]) / 0.25 + s.u[fi][3]) / 512.0, (texfix.dot(P, s.v[fi]) / 0.25 + s.v[fi][3]) / 256.0]
        texfix.face_scales(s.m, s.c, os.path.join(s.tmp, 'none.vmf'))
        s.assertTrue(all(sc == [0.25, 0.25] for sc in s.sc))
        s.assertFalse(any('8192-wide' in x for x in s.c.log))


if __name__ == '__main__':
    unittest.main()
