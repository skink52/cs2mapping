"""mapsanity.py: spawns on floors / in floors / without headroom / over the void, probes, team checks. Runs without CS2.

  python -m unittest discover -s tools/tests -p "test_mapsanity.py" -v
"""
import os, shutil, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
import mapsanity


class Geometry(unittest.TestCase):
    def test_z_at_and_floor(self):
        tri = ((0, 0, 0), (100, 0, 0), (0, 100, 10))
        self.assertAlmostEqual(mapsanity.z_at(tri, 10, 50), 5.0)
        self.assertIsNone(mapsanity.z_at(tri, 90, 90))
        self.assertAlmostEqual(mapsanity.floor_below([tri], (10, 10, 20)), 1.0)
        self.assertIsNone(mapsanity.floor_below([tri], (10, 10, 500)))
        roof = ((-50, -50, 40), (50, -50, 40), (0, 50, 40))
        self.assertEqual(mapsanity.ceiling_above([roof], (0, 0, 0)), 40)
        self.assertIsNone(mapsanity.ceiling_above([roof], (0, 0, -40)))   # 80 above the feet: clear


class FixtureMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.vmap = F.temp_root()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def codes(self, res):
        out = {}
        for f in res['findings']: out.setdefault(f['code'], []).append(f['text'])
        return out

    def test_spawns(self):
        res = mapsanity.run(self.vmap)
        c = self.codes(res)
        self.assertEqual(len(c['spawn_in_floor']), 1); self.assertIn('200 100 0', c['spawn_in_floor'][0])
        self.assertEqual(len(c['spawn_headroom']), 1); self.assertIn('340 340 8', c['spawn_headroom'][0])
        self.assertIn('32.0 u above', c['spawn_headroom'][0])
        self.assertEqual(len(c['spawn_not_on_floor']), 1); self.assertIn('2000 2000 400', c['spawn_not_on_floor'][0])
        self.assertNotIn('100 100 8', ' '.join(sum(c.values(), [])))       # the good spawn
        self.assertEqual(res['errors'], 1)

    def test_lighting_and_world(self):
        c = self.codes(mapsanity.run(self.vmap))
        self.assertIn('1 of 4 spawns', c['probe_uncovered'][0])
        self.assertNotIn('sun_missing', c); self.assertNotIn('sky_missing', c)
        self.assertIn('lightmapres_missing', c); self.assertIn('nav_seed_missing', c)

    def test_modes(self):
        c = self.codes(mapsanity.run(self.vmap, 'classic', min_spawns=2))
        self.assertIn('bombsite_missing', c)
        self.assertEqual(len(c['spawn_count']), 1)                          # CT has 1 < 2; T has 3


if __name__ == '__main__':
    unittest.main()
