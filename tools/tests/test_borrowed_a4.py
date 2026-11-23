"""A4 postfx.py: CS:GO color_correction tables -> .vpost lookup-table layer (or Curves + Saturation), underwater .vpost per fog colour.

  python -m unittest discover -s tools/tests -p "test_borrowed_a4.py" -v
"""
import os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import postfx as P, kv3text, vmapedit as V, watervol, dmx

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def raw_of(lut):
    return (np.clip(lut, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes()


class Ctx:
    def __init__(s, root, addon='zz_test'):
        s.addon = addon; s.root = root; s.content = os.path.join(root, 'content', addon)
        s.files = {}; s.log = []; s.todo = []; s.src = None
    def write(s, rel, data): s.files[rel] = data if isinstance(data, bytes) else data.encode('utf-8')


class Tables(unittest.TestCase):
    def test_read_lut_order(s):
        lut = P.read_lut(raw_of(P.identity_lut()))
        s.assertEqual(lut.shape, (32, 32, 32, 3))
        s.assertAlmostEqual(float(lut[0, 0, 31, 0]), 1.0)       # red changes fastest
        s.assertAlmostEqual(float(lut[31, 0, 0, 2]), 1.0)
        s.assertIsNone(P.read_lut(b'\0' * 100))

    def test_lut_layer_is_the_table(s):
        lut = 1.0 - P.identity_lut()
        doc = kv3text.loads(P.vpost([P.lut_layer(lut)])).root
        lay = doc['m_layers'][0]
        s.assertEqual(lay['_class'], 'CColorLookupColorCorrectionLayer'); s.assertEqual(lay['m_nDim'], 32)
        vals = np.array(lay['m_lut'], dtype=float)
        s.assertEqual(vals.shape, (32 ** 3 * 3,))                # flat floats: a list of triples bakes black
        s.assertLess(np.abs(vals - lut.reshape(-1)).max(), 1e-3)

    def test_weight_blends_to_identity(s):
        lut = 1.0 - P.identity_lut()
        vals = np.array(kv3text.loads(P.vpost([P.lut_layer(lut, 0.5)])).root['m_layers'][0]['m_lut'], dtype=float)
        s.assertLess(np.abs(vals - 0.5).max(), 1e-3)
        s.assertTrue(P.is_identity(P.identity_lut())); s.assertTrue(P.is_identity(lut, 0.0)); s.assertFalse(P.is_identity(lut))

    def test_curves_mode(s):
        dark = P.identity_lut() * 0.5
        lay = P.cc_layers(dark)
        s.assertIn('CCurvesColorCorrectionLayer', lay[0]); s.assertIn('[ 255, 128 ]', lay[0])
        s.assertEqual(P.cc_layers(P.identity_lut()), [])
        grey = np.repeat(P.identity_lut().mean(-1, keepdims=True), 3, -1)
        s.assertTrue(any('m_nSaturation = -' in x for x in P.cc_layers(grey)))

    def test_add_layers(s):
        base = open(P.TEMPLATE_UNDERWATER, encoding='utf-8').read()
        out = P.add_layers(base, [P.layer('CCurvesColorCorrectionLayer', P.CC_NAME, P.curves_body({'R': [(0, 0), (255, 200)]}))])
        doc = kv3text.loads(out).root
        s.assertEqual([l['_class'] for l in doc['m_layers']], ['CCurvesColorCorrectionLayer', 'CToneMappingLayer', 'CBloomLayer'])
        s.assertEqual(P.add_layers(out, ['x']), out)              # ours already there: unchanged


class Underwater(unittest.TestCase):
    def test_fog_colour(s):
        s.assertEqual(P.fog_colour({'$fogcolor': '{51 102 255}'}), (0.2, 0.4, 1.0))
        s.assertEqual(P.fog_colour({'$fogcolor': '[0.1 0.2 0.3]'}), (0.1, 0.2, 0.3))
        s.assertIsNone(P.fog_colour({})); s.assertIsNone(P.fog_colour({'$fogcolor': 'x'}))

    def test_underwater_vpost(s):
        doc = kv3text.loads(P.underwater_vpost((0.0, 0.5, 1.0))).root
        classes = [l['_class'] for l in doc['m_layers']]
        s.assertEqual(classes[:2], ['CCurvesColorCorrectionLayer', 'CVibranceColorCorrectionLayer'])
        s.assertIn('CToneMappingLayer', classes)                  # our filmic template kept
        red = doc['m_layers'][0]['m_curvePointsR']
        s.assertEqual(red[-1], [255, round(255 * 0.55)])           # red pulled down most for blue-green fog


class Step(unittest.TestCase):
    def setUp(s):
        s.tmp = tempfile.mkdtemp(prefix='borrowed_a4_')
        s.c = Ctx(s.tmp)
        os.makedirs(os.path.join(s.c.content, 'materials', 'correction'))
        open(os.path.join(s.c.content, 'materials', 'correction', 'dark.raw'), 'wb').write(raw_of(P.identity_lut() * 0.5))
        s.m = V.Map(watervol.TEMPLATE)

    def tearDown(s): shutil.rmtree(s.tmp, ignore_errors=True)

    def vmf(s, ents):
        p = os.path.join(s.tmp, 'm.vmf')
        open(p, 'w').write(''.join('entity\n{\n%s}\n' % ''.join('\t"%s" "%s"\n' % kv for kv in e.items()) for e in ents))
        return p

    def test_global_makes_master(s):
        v = s.vmf([{'classname': 'color_correction', 'origin': '0 0 0', 'filename': 'materials/correction/dark.raw', 'maxweight': '1',
                    'minfalloff': '-1', 'maxfalloff': '-1'}])
        s.assertEqual(P.color_correction(s.m, s.c, v), 1)
        rel = 'lighting/postprocessing/zz_test_cc_1.vpost'
        s.assertIn(rel, s.c.files)
        s.assertEqual(kv3text.loads(s.c.files[rel].decode()).root['m_layers'][0]['_class'], 'CColorLookupColorCorrectionLayer')
        pv = s.m.by_class('post_processing_volume')
        s.assertEqual(len(pv), 1); s.assertEqual(s.m.P(pv[0], 'master'), '1'); s.assertEqual(s.m.P(pv[0], 'postprocessing'), rel)
        s.assertTrue(any(s.m.type(ch) == b'CMapMesh' for ch in s.m.children(pv[0])))

    def test_falloff_box_and_named(s):
        v = s.vmf([{'classname': 'color_correction', 'origin': '100 0 0', 'filename': 'materials/correction/dark.raw', 'minfalloff': '128', 'maxfalloff': '512'},
                   {'classname': 'color_correction', 'origin': '0 0 0', 'targetname': 'cc_switch', 'filename': 'materials/correction/dark.raw'},
                   {'classname': 'color_correction', 'origin': '0 0 0', 'filename': 'materials/correction/missing.raw'}])
        s.assertEqual(P.color_correction(s.m, s.c, v, mode='curves'), 2)
        pv = s.m.by_class('post_processing_volume')
        s.assertEqual(len(pv), 1); s.assertEqual(s.m.P(pv[0], 'master'), '0')
        lo, hi = s.m.bounds(pv[0])
        s.assertEqual((round(lo[0]), round(hi[0])), (-412, 612))
        s.assertIn('cc_switch', ' '.join(s.c.todo)); s.assertIn('missing.raw', ' '.join(s.c.todo))
        s.assertIn('CCurvesColorCorrectionLayer', s.c.files['lighting/postprocessing/zz_test_cc_1.vpost'].decode())

    def test_underwater_step(s):
        os.makedirs(os.path.join(s.tmp, 'embedded', 'zz_test', 'materials', 'water'))
        open(os.path.join(s.tmp, 'embedded', 'zz_test', 'materials', 'water', 'pool.vmt'), 'w').write('"Water"\n{\n"$fogcolor" "{20 80 90}"\n}\n')
        tm = V.Map(watervol.TEMPLATE); tnode = tm.children(tm.world)[0]
        w = s.m.new_entity('func_water', [0, 0, 0], {})
        dmx.geta(s.m.E[w], b'children')[2].append(watervol.box(s.m, tm, tnode, [-100, -100, -200], [100, 100, 0], b'materials/water/pool.vmat'))
        pv = s.m.new_entity('post_processing_volume', [0, 0, -100], {'postprocessing': P.UNDERWATER_VPOST, 'master': '0'})
        other = s.m.new_entity('post_processing_volume', [5000, 0, 0], {'postprocessing': P.UNDERWATER_VPOST, 'master': '0'})
        s.assertEqual(P.underwater(s.m, s.c), 1)
        s.assertEqual(s.m.P(pv, 'postprocessing'), 'lighting/postprocessing/zz_test_underwater_1.vpost')
        s.assertEqual(s.m.P(other, 'postprocessing'), P.UNDERWATER_VPOST)    # no water found: shared vpost kept
        s.assertIn('Water Colour', s.c.files['lighting/postprocessing/zz_test_underwater_1.vpost'].decode())


if __name__ == '__main__':
    unittest.main()
