"""Fixes to the cs2-map-mcp toolset found while building mg_ironframe_sprawl (10 Nov 2026, guide section 9):
mapops per-face materials, a clear error when cuts remove a whole shape, fxkit lightning flash strength, the func_precipitation warning.

  python -m unittest discover -s tools/tests -p "test_toolset_sprawl.py" -v
"""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
sys.path.insert(0, F.CREATE)
import mapops, primitives as P


class PerFaceMaterials(unittest.TestCase):
    def test_box_top_side_bottom(self):
        s = mapops.shape({'shape': 'box', 'mins': [0, 0, 0], 'maxs': [100, 50, 300], 'material': 'm/base.vmat',
                          'materials': {'top': 'm/top.vmat', 'side': 'm/side.vmat'}})
        by = {}
        for i, loop in enumerate(s[1]):
            n = P._unit(P.newell(s[0], loop)); by.setdefault('top' if n[2] > 0.7 else 'bottom' if n[2] < -0.7 else 'side', set()).add(s[2][i])
        self.assertEqual(by, {'top': {'m/top.vmat'}, 'side': {'m/side.vmat'}, 'bottom': {'m/base.vmat'}})     # bottom left out: kept

    def test_mesh_edit_keeps_per_face_materials(self):
        s, uvs, paint = mapops.mesh_edit({'op': 'mesh_edit', 'shape': {'shape': 'box', 'mins': [0, 0, 0], 'maxs': [64, 64, 64],
                                                                       'materials': {'side': 'm/side.vmat', 'top': 'm/top.vmat', 'bottom': 'm/b.vmat'}},
                                          'uv': {'scale': 2.0}})
        self.assertEqual(set(s[2]), {'m/side.vmat', 'm/top.vmat', 'm/b.vmat'})
        self.assertEqual(P.check(s), [])

    def test_unknown_face_key(self):
        with self.assertRaises(ValueError): mapops.shape({'shape': 'box', 'mins': [0, 0, 0], 'maxs': [1, 1, 1], 'materials': {'front': 'x'}})


class Cuts(unittest.TestCase):
    def test_cut_removing_everything_is_explained(self):
        with self.assertRaises(ValueError) as e:
            mapops.mesh_edit({'op': 'mesh_edit', 'shape': {'shape': 'box', 'mins': [0, 0, 0], 'maxs': [10, 10, 10]},
                              'cut': [{'shape': 'box', 'mins': [-1, -1, -1], 'maxs': [11, 11, 11]}]})
        self.assertIn('removed the whole shape', str(e.exception))

    def test_staggered_cells_stay_manifold(self):
        """the Sprawl ruin cut: 3 x 3 cells at different heights; staggered rows keep the solid manifold"""
        cells = []
        for j in range(3):
            xs = [-12, 100 + (j - 1) * 27, 200 + (j - 1) * 27, 312]
            for i in range(3): cells.append({'shape': 'box', 'mins': [xs[i], j * 100 - (12 if j == 0 else 0), 2 + 5 * ((i * 7 + j * 3) % 4)],
                                             'maxs': [xs[i + 1], (j + 1) * 100 + (12 if j == 2 else 0), 50]})
        s, _, _ = mapops.mesh_edit({'op': 'mesh_edit', 'shape': {'shape': 'box', 'mins': [0, 0, 0], 'maxs': [300, 300, 18]}, 'cut': cells})
        self.assertEqual(P.check(s), [])


LIGHTNING = r'''
import os, sys
sys.path.insert(0, CREATE)
import vmapgen, fxkit
d = vmapgen.open_map(os.path.join(TOOLS, 'box_template.vmap'), os.path.dirname(OUT))
fxkit.lightning('dim', (0, 0, 600), alpha=55, group='t')
r = fxkit.precipitation(((0, 0, 0), (512, 512, 512)), 'rain', 'rain1', group='t')
assert 'exclude' in r['warning'], r
vmapgen.finish(d, OUT, group='t')
'''


class Lightning(unittest.TestCase):
    @unittest.skipUnless(__import__('fgdcat').fgd_paths(), 'CS2 not installed (the map build reads its FGDs)')
    def test_flash_strength(self):
        tmp = tempfile.mkdtemp(prefix='cs2mcp_sprawl_')
        out = F.make_map(os.path.join(tmp, 'fx.vmap'), LIGHTNING)
        import vmapedit as V
        m = V.Map(out)
        fade = m.by_class('env_fade')[0]
        self.assertEqual(str(m.P(fade, 'renderamt')), '55')


if __name__ == '__main__':
    unittest.main()
