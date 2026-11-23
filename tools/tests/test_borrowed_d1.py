"""D1 assets.py: a CS:GO WorldVertexTransition material is rebuilt as a two-layer csgo_lightmappedgeneric vmat (as Valve's importer
writes it), and upgrade_blends rewrites earlier one-layer rebuilds.

  python -m unittest discover -s tools/tests -p "test_borrowed_d1.py" -v
"""
import os, shutil, struct, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import assets, blendpaint


def vtf_rgb(w=4, h=4, rgb=(10, 20, 30)):
    """minimal VTF 7.2, RGB888, one mip, no low-res image"""
    hd = bytearray(80); hd[0:4] = b'VTF\0'
    struct.pack_into('<III', hd, 4, 7, 2, 80)
    struct.pack_into('<HHIHH', hd, 16, w, h, 0, 1, 0)
    struct.pack_into('<iBiBB', hd, 52, 2, 1, -1, 0, 0)
    struct.pack_into('<H', hd, 63, 1)
    return bytes(hd) + bytes(rgb) * (w * h)


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


WVT = b'''"WorldVertexTransition"
{
    "$basetexture" "nature/dirt01"
    "$basetexture2" "nature/grass01"
    "$bumpmap" "nature/dirt01_normal"
    "$blendmodulatetexture" "nature/dirt_blend"
    "$surfaceprop" "dirt"
    "$surfaceprop2" "grass"
}
'''
PLAIN_WVT = b'"WorldVertexTransition"\n{\n "$basetexture" "nature/a"\n "$basetexture2" "nature/b"\n}\n'
SSB_WVT = b'"WorldVertexTransition"\n{\n "$basetexture" "nature/a"\n "$basetexture2" "nature/b"\n "$bumpmap" "nature/a_ssb"\n "$ssbump" "1"\n}\n'


class Blend(unittest.TestCase):
    def setUp(s):
        s.tmp = tempfile.mkdtemp(); s.c = Ctx(s.tmp); os.makedirs(s.c.content)
        files = {'materials/nature/blend.vmt': WVT, 'materials/nature/plain.vmt': PLAIN_WVT, 'materials/nature/ssb.vmt': SSB_WVT}
        for t in ('nature/dirt01', 'nature/grass01', 'nature/dirt01_normal', 'nature/dirt_blend', 'nature/a', 'nature/b', 'nature/a_ssb'):
            files['materials/%s.vtf' % t] = vtf_rgb()
        s.vpk = FakeVPK(files)
        s._mm = assets.mesh_materials
    def tearDown(s):
        assets.mesh_materials = s._mm; shutil.rmtree(s.tmp, ignore_errors=True)

    def use(s, *mats):
        assets.mesh_materials = lambda m: {x: [0] for x in mats}

    def test_two_layers_like_the_importer(s):
        s.use('materials/nature/blend.vmat')
        stock = FakeVPK({})
        assets.fix_materials(None, s.c, stock, s.vpk, {})
        t = s.c.files['materials/nature/blend.vmat'].decode()
        for k in ('"Shader"\t\t"csgo_lightmappedgeneric.vfx"', '"F_LAYERS"\t\t"1"', '"TextureLayer1Color"\t\t"materials/nature/dirt01.png"',
                  '"TextureLayer2Color"\t\t"materials/nature/grass01.png"', '"TextureBlendModulation"\t\t"materials/nature/dirt_blend.png"',
                  '"F_FANCY_BLENDING"\t\t"1"', '"TextureLayer1Normal"\t\t"materials/nature/dirt01_normal_normal.tga"',
                  '"PhysicsSurfaceProperties2"\t\t"grass"'):
            s.assertIn(k, t)
        s.assertNotIn('TextureLayer2Normal', t)                      # no $bumpmap2: no layer-2 normal (importer form)
        s.assertNotIn('csgo_complex', t)
        s.assertIn('legacy_source1_inverted_normal', s.c.files['materials/nature/dirt01_normal_normal.txt'].decode())
        for p in ('materials/nature/dirt01.png', 'materials/nature/grass01.png', 'materials/nature/dirt_blend.png'): s.assertIn(p, s.c.files)
        s.assertTrue(any('two-layer' in l and 'blend' in l for l in s.c.log))
        p = os.path.join(s.tmp, 'out.vmat')
        with open(p, 'wb') as fh: fh.write(s.c.files['materials/nature/blend.vmat'])
        s.assertEqual(blendpaint.vmat_layers(p), 2)

    def test_no_modulation_and_ssbump(s):
        r = assets.write_blend(s.c, assets.Source(s.c, s.vpk, {}), 'materials/nature/plain.vmat', 'materials/nature/plain.vmt',
                               assets.parse_vmt(PLAIN_WVT.decode())[1])
        s.assertTrue(r)
        t = s.c.files['materials/nature/plain.vmat'].decode()
        s.assertIn('"F_FANCY_BLENDING"\t\t"0"', t); s.assertNotIn('TextureBlendModulation', t); s.assertNotIn('Normal"', t)
        kv = assets.parse_vmt(SSB_WVT.decode())[1]
        assets.write_blend(s.c, assets.Source(s.c, s.vpk, {}), 'materials/nature/ssb.vmat', 'materials/nature/ssb.vmt', kv)
        s.assertIn('materials/nature/a_ssb_ssbn.tga', s.c.files['materials/nature/ssb.vmat'].decode())

    def test_waits_for_vpk_chunk(s):
        class Chunked(FakeVPK):
            def archive_of(s2, p): return 3
        v = Chunked(s.vpk.data); s.c.need_paths = set()
        r = assets.write_blend(s.c, assets.Source(s.c, v, {}), 'materials/nature/blend.vmat', 'materials/nature/blend.vmt',
                               assets.parse_vmt(WVT.decode())[1])
        s.assertIsNone(r); s.assertIn(3, s.c.need); s.assertNotIn('materials/nature/blend.vmat', s.c.files)

    def test_upgrade_only_our_one_layer_rebuilds(s):
        d = os.path.join(s.c.content, 'materials', 'nature'); os.makedirs(d)
        ours = '// Rebuilt from CS:GO materials/nature/blend.vmt (basetexture nature/dirt01).\nLayer0\n{\n    shader "csgo_complex.vfx"\n}\n'
        hand = 'Layer0\n{\n    shader "csgo_complex.vfx"\n}\n'
        with open(os.path.join(d, 'blend.vmat'), 'w') as fh: fh.write(ours)
        with open(os.path.join(d, 'plain.vmat'), 'w') as fh: fh.write(hand)
        s.use('materials/nature/blend.vmat', 'materials/nature/plain.vmat')
        done = assets.upgrade_blends(None, s.c, s.vpk, {})
        s.assertEqual(done, ['materials/nature/blend.vmat'])
        s.assertIn('F_LAYERS', s.c.files['materials/nature/blend.vmat'].decode())
        s.assertNotIn('materials/nature/plain.vmat', s.c.files)        # hand-made vmat never touched
        s.c.files.clear()
        with open(os.path.join(d, 'blend.vmat'), 'wb') as fh: fh.write(assets.blend_vmat('x', {}, 'a', 'b').encode())
        s.assertEqual(assets.upgrade_blends(None, s.c, s.vpk, {}), [])   # already two layers: rerun is a no-op

    def test_cli_refuses_out_inside_addon(s):
        with s.assertRaises(SystemExit):
            assets.main(['upgrade-blends', 'x.vmap', s.c.content, os.path.join(s.c.content, 'sub')])


if __name__ == '__main__':
    unittest.main()
