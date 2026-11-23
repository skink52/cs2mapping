"""B1 blendpaint.py: displacement alphas from a VMF -> VertexPaintBlendParams on a plain mesh (disprestore's output), and the grid maths.

  python -m unittest discover -s tools/tests -p "test_borrowed_b1.py" -v
"""
import os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import blendpaint as B, vmapedit as V, watervol, dmx

ROW = lambda vals: ' '.join('%g' % v for v in vals)


def vmf_text(alphas, power=2):
    n = (1 << power) + 1
    rows = lambda blk, w, f: '\t\t\t\t%s\n\t\t\t\t{\n%s\t\t\t\t}\n' % (blk, ''.join('\t\t\t\t\t"row%d" "%s"\n' % (i, ROW(f(i))) for i in range(n)))
    disp = ('\t\t\tdispinfo\n\t\t\t{\n\t\t\t\t"power" "%d"\n\t\t\t\t"startposition" "[0 0 0]"\n\t\t\t\t"elevation" "0"\n' % power
            + rows('normals', 3, lambda i: [0, 0, 1] * n) + rows('distances', 1, lambda i: [0] * n) + rows('alphas', 1, lambda i: alphas[i])
            + '\t\t\t}\n')
    planes = [('(0 0 0) (0 128 0) (128 128 0)', disp),            # top, z = 0
              ('(0 128 -16) (0 0 -16) (128 0 -16)', ''), ('(0 0 0) (0 0 -16) (0 128 -16)', ''), ('(128 128 0) (128 128 -16) (128 0 -16)', ''),
              ('(128 0 0) (128 0 -16) (0 0 -16)', ''), ('(0 128 0) (0 128 -16) (128 128 -16)', '')]
    sides = ''.join('\t\tside\n\t\t{\n\t\t\t"plane" "%s"\n\t\t\t"material" "NATURE/BLENDTEST"\n%s\t\t}\n' % (p, d) for p, d in planes)
    return 'world\n{\n\t"classname" "worldspawn"\n\tsolid\n\t{\n%s\t}\n}\n' % sides


class GridMaths(unittest.TestCase):
    def test_inverse_bilinear(self):
        q = [(0, 0), (2, 0), (2, 3), (0, 3)]
        s, t = B._inv_bilinear((0.5, 2.25), q)
        self.assertAlmostEqual(s, 0.25, 4); self.assertAlmostEqual(t, 0.75, 4)

    def test_alpha_interpolates(self):
        d = B.Disp('x', 2, [[0, 0, 0], [0, 255, 0], [0, 0, 0]], [None, None])
        self.assertAlmostEqual(d.alpha(1, 1), 255); self.assertAlmostEqual(d.alpha(0.5, 1), 127.5)

    def test_material_names(self):
        self.assertEqual(B.norm_mat('materials/Nature/Blend Test.vmat'), 'nature/blend_test')
        self.assertEqual(B.norm_mat('NATURE/BLENDTEST'), 'nature/blendtest')


class PlainMesh(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.alphas = [[255, 0, 0, 0, 40], [0] * 5, [0] * 5, [0] * 5, [40, 0, 0, 0, 100]]
        self.vmf = os.path.join(self.tmp, 't.vmf')
        with open(self.vmf, 'w') as fh: fh.write(vmf_text(self.alphas))

    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_vmf_grid(self):
        ds = B.vmf_disps(self.vmf)
        self.assertEqual(len(ds), 1); d = ds[0]
        self.assertEqual((d.mat, d.n), ('nature/blendtest', 4))
        corners = sorted(tuple(round(float(x)) for x in d.grids[0][i, j]) for i, j in ((0, 0), (4, 0), (4, 4), (0, 4)))
        self.assertEqual(corners, [(0, 0, 0), (0, 128, 0), (128, 0, 0), (128, 128, 0)])
        self.assertEqual(tuple(round(float(x)) for x in d.grids[0][0, 0]), (0, 0, 0))   # start corner

    def test_paint_box_top(self):
        m = V.Map(watervol.TEMPLATE)
        tm = V.Map(watervol.TEMPLATE)
        j = watervol.box(m, tm, tm.children(tm.world)[0], [0, 0, -16], [128, 128, 0], b'materials/nature/blendtest.vmat')
        dmx.geta(m.E[m.world], b'children')[2].append(j)
        log = []
        st, single = B.run(m, self.vmf, log=log)
        self.assertEqual(st['plain_meshes'], 1); self.assertEqual(st['plain_faces'], 1)
        self.assertTrue(log and log[0].startswith('blendpaint:'))
        md = m.g(j, b'meshData'); fvd = m.g(md, b'faceVertexData')
        vals = m.g(B._streams(m, fvd)[B.STREAM], b'data')
        self.assertEqual(len(vals), m.g(fvd, b'size'))
        self.assertEqual(sorted(round(v[0] * 255) for v in vals if v[0] > 0), [40, 40, 100, 255])
        # kept on a second run (already painted), overwritten only with force
        st2, _ = B.run(m, self.vmf); self.assertEqual((st2['plain_meshes'], st2['kept']), (0, 1))
        out = os.path.join(self.tmp, 'o.vmap'); m.save(out)
        m2 = V.Map(out); self.assertTrue(any(B.STREAM in B._streams(m2, m2.g(m2.g(n, b'meshData'), b'faceVertexData'))
                                             for n, _ in m2.walk() if m2.type(n) == b'CMapMesh'))

    def test_single_layer_report(self):
        p = os.path.join(self.tmp, 'a.vmat'); open(p, 'w').write('Layer0\n{\n shader "csgo_complex.vfx"\n}\n')
        self.assertEqual(B.vmat_layers(p), 1)
        with open(p, 'w') as fh: fh.write('"Layer0"\n{\n"Shader" "csgo_lightmappedgeneric.vfx"\n"F_LAYERS" "1"\n}\n')
        self.assertEqual(B.vmat_layers(p), 2)


if __name__ == '__main__':
    unittest.main()
