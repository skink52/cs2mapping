"""visualcheck.py: floating props, props in walls, props inside props, z-fighting (zfight.py), open meshes; bounds reader and cache.
Model bounds come from a stand-in reader, so no Node run and no CS2 files are needed.

  python -m unittest discover -s tools/tests -p "test_visualcheck.py" -v
"""
import json, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
import visualcheck as VC

BUILD = r'''
import os, sys
sys.path.insert(0, CREATE)
import vmapgen, vmaplib, primitives as P
P.CATALOG = None
d = vmapgen.open_map(os.path.join(TOOLS, 'box_template.vmap'), os.path.dirname(OUT))
P.add(P.box((0, 0, -32), (1024, 1024, 0)), group='t')                               # floor, top z 0
P.add(P.box((300, 300, 0), (380, 380, 128)), group='t')                             # a pillar
P.add(P.box((600, 600, 0), (700, 700, 64), 'materials/a.vmat'), group='t')          # two boxes sharing a top face: z-fighting
P.add(P.box((620, 620, 40), (680, 680, 64), 'materials/b.vmat'), group='t')        # its top is in the same plane as the box above
def prop(name, model, origin):
    vmaplib.ent('prop_static', origin, group='t', targetname=name, model=model, solid='6')
prop('ok', 'models/crate.vmdl', (100, 100, 0))
prop('floating', 'models/crate.vmdl', (100, 300, 100))
prop('in_wall', 'models/crate.vmdl', (300, 340, 32))
prop('touching_wall', 'models/crate.vmdl', (396, 340, 60))                          # hangs, but its side touches the pillar
prop('a', 'models/crate.vmdl', (800, 100, 0))
prop('b', 'models/barrel.vmdl', (804, 104, 0))                                        # inside crate a
prop('stacked', 'models/barrel.vmdl', (100, 100, 32))                                 # on top of crate ok: supported
prop('cache_x', 'models/crate.vmdl', (5000, 5000, 5000))                              # precache room: skipped
prop('nobounds', 'models/unknown.vmdl', (900, 900, 0))
vmapgen.finish(d, OUT, group='t')
'''

BOUNDS = {'models/crate.vmdl_c': {'lo': [-16, -16, 0], 'hi': [16, 16, 32]}, 'models/barrel.vmdl_c': {'lo': [-12, -12, 0], 'hi': [12, 12, 40]}}


class Visual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = F.fake_cs2(tempfile.mkdtemp(prefix='cs2mcp_vis_'))
        cls.vmap = F.make_map(os.path.join(cls.root, 'content', 'csgo_addons', 'test_addon', 'maps', 'vis.vmap'), BUILD)
        cls.asked = []
        def reader(items):
            cls.asked.append(items)
            return {p: BOUNDS[p] for p, _ in items if p in BOUNDS}
        cls.cache = os.path.join(cls.root, 'bounds.json')
        os.environ['CS2_ROOT'] = cls.root
        cls.mb = VC.ModelBounds(cls.root, 'test_addon', cls.cache, reader)
        cls.res = VC.run(cls.vmap, bounds=cls.mb)
        cls.by = {}
        for f in cls.res['findings']: cls.by.setdefault(f['code'], []).append(f['text'])

    @classmethod
    def tearDownClass(cls):
        os.environ.pop('CS2_ROOT', None)
        shutil.rmtree(cls.root, ignore_errors=True)

    def names(self, code):
        return ' '.join(self.by.get(code, []))

    def test_floating(self):
        self.assertIn('at 100 300 100', self.names('prop_floating'))
        self.assertNotIn('396 340', self.names('prop_floating'))                 # wall contact
        self.assertNotIn('at 100 100 32', self.names('prop_floating'))           # stands on the crate below
        self.assertEqual(len(self.by['prop_floating']), 1)

    def test_in_geometry_and_overlap(self):
        self.assertIn('at 300 340 32', self.names('prop_in_geometry'))
        self.assertEqual(len(self.by['prop_in_geometry']), 1)
        self.assertTrue('crate' in self.names('prop_overlap') and 'barrel' in self.names('prop_overlap'))
        self.assertEqual(len(self.by['prop_overlap']), 1)

    def test_zfight_unknown_cache(self):
        self.assertTrue(any('materials/a.vmat' in t and 'materials/b.vmat' in t for t in self.by.get('z_fighting', [])), self.by.get('z_fighting'))
        self.assertIn('models/unknown.vmdl', self.names('bounds_unknown'))
        self.assertNotIn('5000', ' '.join(sum(self.by.values(), [])))
        with open(self.cache) as f: cached = json.load(f)
        self.assertIsNone(cached['models/unknown.vmdl'])
        self.assertEqual(cached['models/crate.vmdl'], [[-16, -16, 0], [16, 16, 32]])
        n = len(self.asked)
        VC.ModelBounds(self.root, 'test_addon', self.cache, lambda items: self.fail('cache not used')).get_many(['models/crate.vmdl'])
        self.assertEqual(len(self.asked), n)

    def test_source_smd_fallback(self):
        addon = os.path.join(self.root, 'content', 'csgo_addons', 'test_addon')
        os.makedirs(os.path.join(addon, 'models', 'own'), exist_ok=True)
        F.write(os.path.join(addon, 'models', 'own', 'thing.vmdl'), 'RenderMeshFile { filename = "models/own/thing.smd" import_scale = 2.0 }')
        F.write(os.path.join(addon, 'models', 'own', 'thing.smd'), 'version 1\ntriangles\nmat\n0 -1 -2 0 0 0 1 0 0\n0 1 2 3 0 0 1 0 0\n0 0 0 1 0 0 1 0 0\nend\n')
        mb = VC.ModelBounds(self.root, 'test_addon', os.path.join(self.root, 'b2.json'), lambda items: {})
        self.assertEqual(mb.get_many(['models/own/thing.vmdl'])['models/own/thing.vmdl'], [[-2.0, -4.0, 0.0], [2.0, 4.0, 6.0]])

    def test_tri_box(self):
        self.assertTrue(VC.tri_box(((-20, 0, -20), (20, 0, -20), (0, 0, 20)), (5, 5, 5)))
        self.assertFalse(VC.tri_box(((-20, 9, -20), (20, 9, -20), (0, 9, 20)), (5, 5, 5)))
        self.assertFalse(VC.tri_box(((6, 6, -1), (20, 6, -1), (6, 20, -1)), (5, 5, 5)))


if __name__ == '__main__':
    unittest.main()
