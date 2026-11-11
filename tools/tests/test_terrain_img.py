"""create/terrain_img.py and create/refimg.py: height images round trip, the ported terrain ops, erosion keeps protected ground
exactly as it was, flow gathers downhill, paint / density images, reference sheets. Small grids, no CS2 needed.

  python -m unittest discover -s tools/tests -p "test_terrain_img.py" -v
"""
import json, os, shutil, sys, tempfile, unittest
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
sys.path.append(F.CREATE)
import terrain_img as TI
import refimg

B = (-1024.0, -768.0, 1024.0, 768.0)


def hillside(X, Y):
    """an even slope down to the south with a low ridge and a hollow"""
    return 0.25 * (Y + 768) + 30 * np.exp(-((X - 300) ** 2 + (Y - 100) ** 2) / 200.0 ** 2) - 25 * np.exp(-((X + 400) ** 2 + (Y + 200) ** 2) / 150.0 ** 2)


class Images(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp()
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)

    def test_field_png_roundtrip(self):
        f = TI.Field.from_fn(hillside, B, 32)
        self.assertEqual(f.Z.shape, (65, 49))
        p = os.path.join(self.d, 'h.png'); meta = f.save(p)
        with Image.open(p) as im:
            self.assertEqual(im.mode, 'I;16'); self.assertEqual(im.size, (65, 49))      # column = x step, row = y step
        g = TI.Field.load(p)
        self.assertLess(np.abs(g.Z - f.Z).max(), meta['step'])
        self.assertEqual(g.bounds, f.bounds)
        # row 0 is the lowest y: the south edge is the low end of this slope
        with Image.open(p) as im: px = np.asarray(im)
        self.assertLess(px[0].mean(), px[-1].mean())

    def test_zero_is_exact_in_a_detail_png(self):
        Z = np.zeros((65, 49)); Z[10:20, 10:20] = 17.3; Z[30:40, 5:9] = -41.7
        f = TI.Field(Z, B, 32); p = os.path.join(self.d, 'd.png'); f.save(p, -50, 50)
        g = TI.Field.load(p)
        self.assertEqual(float(np.abs(g.Z[Z == 0]).max()), 0.0)
        self.assertAlmostEqual(float(g.Z[12, 12]), 17.3, delta=0.01)

    def test_load_like_upstream(self):
        """an 8-bit image + height_range, resized to the grid (cs2-map-mcp's heightmap option)"""
        a = np.tile(np.linspace(0, 255, 33).astype(np.uint8), (25, 1))        # brighter to the east
        p = os.path.join(self.d, 'h8.png'); Image.fromarray(a).save(p)
        f = TI.Field.load(p, bounds=B, cell=32, height_range=[100, 300])
        self.assertEqual(f.Z.shape, (65, 49))
        self.assertAlmostEqual(float(f.Z[0, 10]), 100, delta=2); self.assertAlmostEqual(float(f.Z[-1, 10]), 300, delta=2)
        with self.assertRaises(ValueError): TI.Field.load(p)
        Image.new('RGB', (4, 4)).save(os.path.join(self.d, 'c.png'))
        with self.assertRaises(ValueError): TI.Field.load(os.path.join(self.d, 'c.png'), bounds=B, height_range=[0, 1])

    def test_sampler(self):
        f = TI.Field.from_fn(lambda X, Y: 2 * X + 3 * Y, B, 32)
        x = np.array([-1000.5, 3.25, 777.0]); y = np.array([-700.0, 11.5, 600.75])
        np.testing.assert_allclose(f(x, y), 2 * x + 3 * y, atol=1e-6)        # bilinear is exact on a plane
        self.assertAlmostEqual(float(f(5000.0, 0.0)), 2 * 1024, places=6)    # clamped outside
        with self.assertRaises(ValueError): TI.Field(np.zeros((3, 3)), B, 32)

    def test_ops(self):
        f = TI.Field(np.zeros((65, 49)), B, 32)
        g = TI.apply_ops(f, [{'op': 'hill', 'center': [0, 0], 'radius': 400, 'height': 100}])
        self.assertAlmostEqual(float(g(0.0, 0.0)), 100, delta=0.5); self.assertEqual(float(g(900.0, 0.0)), 0.0)
        g = TI.apply_ops(f, [{'op': 'valley', 'center': [0, 0], 'radius': 400, 'height': 100}])
        self.assertAlmostEqual(float(g(0.0, 0.0)), -100, delta=0.5)
        g = TI.apply_ops(f, [{'op': 'ridge', 'path': [[-800, 0], [800, 0]], 'width': 256, 'height': 40}])
        self.assertAlmostEqual(float(g(100.0, 0.0)), 40, delta=0.5); self.assertEqual(float(g(100.0, 400.0)), 0.0)
        g = TI.apply_ops(f, [{'op': 'plateau', 'polygon': [[-256, -256], [256, -256], [256, 256], [-256, 256]], 'z': 64, 'falloff': 128}])
        self.assertEqual(float(g(0.0, 0.0)), 64.0); self.assertEqual(float(g(800.0, 0.0)), 0.0)
        self.assertTrue(0 < float(g(320.0, 0.0)) < 64)
        s = TI.Field.from_fn(lambda X, Y: 0.1 * X + 20 * np.sin(Y / 90.0), B, 32)
        g = TI.apply_ops(s, [{'op': 'flatten', 'path': [[-800, 0], [800, 0]], 'width': 200, 'z': 'follow', 'falloff': 96}])
        xs = np.linspace(-700, 700, 9)
        np.testing.assert_allclose(g(xs, np.full(9, 64.0)), g(xs, np.zeros(9)), atol=1e-6)      # level across the road bed
        self.assertAlmostEqual(float(g(0.0, 0.0)), 0.0, delta=1.0)                              # graded between the ends
        n = TI.apply_ops(f, [{'op': 'noise', 'amplitude': 10, 'scale': 150, 'seed': 3}])
        self.assertGreater(float(n.Z.std()), 0.5); self.assertLess(float(np.abs(n.Z).max()), 20)
        with self.assertRaises(ValueError): TI.apply_ops(f, [{'op': 'nope'}])

    def test_level_by_painted_mask(self):
        m = np.zeros((49, 65), np.uint8); m[20:30, 20:40] = 255                # an image: [row = y, column = x]
        p = os.path.join(self.d, 'm.png'); Image.fromarray(m).save(p)
        f = TI.Field.from_fn(hillside, B, 32)
        g = TI.apply_ops(f, [{'op': 'level', 'mask': p, 'z': 'mean', 'falloff': 96}])
        patch = g.Z[20:40, 20:30]
        self.assertLess(float(patch.max() - patch.min()), 1e-9)
        self.assertEqual(float(np.abs(g.Z[0:10, 40:48] - f.Z[0:10, 40:48]).max()), 0.0)

    def test_masks_and_feather(self):
        X, Y = TI.Field.grid(B, 32)
        m = TI.discs(X, Y, [(0, 0, 200)]) | TI.along(X, Y, [(40, [(-900, 500), (900, 500)])])
        self.assertTrue(m[32, 24]); self.assertTrue(m[10, 40]); self.assertFalse(m[2, 2])
        w = TI.feather(m, 6)
        self.assertEqual(float(w[m].min()), 1.0)
        self.assertEqual(float(w[2, 2]), 0.0)
        ring = (np.hypot(X, Y) > 300) & (np.hypot(X, Y) < 400)                # outside the grown mask, inside the feather
        self.assertTrue(((w[ring] > 0) & (w[ring] < 1)).all())
        self.assertTrue(TI.below(np.array([[1.0, 5.0]]), 2.0).tolist() == [[True, False]])


class Erosion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = TI.Field.from_fn(hillside, B, 32)
        X, Y = cls.f.XY
        cls.hard = TI.discs(X, Y, [(300, 100, 260)]) | TI.along(X, Y, [(48, [(-900, -500), (900, -400)])])
        cls.recipe = {'gully_passes': 2, 'drops': 1.0, 'drop_steps': 24, 'thermal_iters': 6, 'seed': 4}
        cls.D, cls.info = TI.detail(cls.f, TI.feather(cls.hard, 4), cls.recipe)

    def test_flow_gathers_downhill(self):
        A = TI.flow(self.f.Z, 32)
        self.assertGreaterEqual(float(A.min()), 1.0 - 1e-9)
        self.assertGreater(float(A[:, 1].mean()), 5 * float(A[:, -2].mean()))          # the foot of the slope collects more than the top
        V = TI.Field.from_fn(lambda X, Y: np.abs(X) * 0.3 + (Y + 768) * 0.05, B, 32)   # a V valley draining south
        A = TI.flow(V.Z, 32)
        self.assertGreater(float(A[32, 2]), 50 * float(np.median(A)))

    def test_fill_pits(self):
        Z = self.f.Z.copy(); Z[30, 20] -= 40
        S = TI.fill_pits(Z)
        self.assertGreater(float(S[30, 20]), float(Z[30, 20]) + 30)
        self.assertTrue((S >= Z - 1e-12).all())
        low = np.minimum.reduce([TI._nb(S, di, dj) for di, dj, _ in TI._NB8])
        inner = np.s_[1:-1, 1:-1]
        self.assertTrue((low[inner] < S[inner]).all())                     # every inner cell has somewhere lower to drain to

    def test_protected_ground_is_untouched(self):
        self.assertEqual(float(np.abs(self.D.Z[self.hard]).max()), 0.0)
        self.assertGreater(float(np.abs(self.D.Z[~self.hard]).max()), 2.0)            # and it did erode elsewhere
        rng = np.random.RandomState(2)                                                # also between grid points
        x = rng.uniform(B[0], B[2], 20000); y = rng.uniform(B[1], B[3], 20000)
        inside = TI.discs(x, y, [(300, 100, 260)]) | TI.along(x, y, [(48, [(-900, -500), (900, -400)])])
        self.assertEqual(float(np.abs(self.D(x, y))[inside].max()), 0.0)

    def test_limits_and_repeatable(self):
        self.assertGreaterEqual(float(self.D.Z.min()), -TI.RECIPE['max_cut']); self.assertLessEqual(float(self.D.Z.max()), TI.RECIPE['max_fill'])
        self.assertTrue(np.isfinite(self.D.Z).all())
        D2, _ = TI.detail(self.f, TI.feather(self.hard, 4), self.recipe)
        np.testing.assert_array_equal(D2.Z, self.D.Z)

    def test_gullies_cut_where_water_runs(self):
        V = TI.Field.from_fn(lambda X, Y: np.abs(X) * 0.3 + (Y + 768) * 0.15, B, 32)
        Z, A = TI.gullies(V.Z, 32, depth=20)
        cut = V.Z - Z
        self.assertTrue((cut >= -1e-9).all())
        self.assertGreater(float(cut[32, 10]), 8.0)                        # the valley line
        self.assertLess(float(cut[5, 40]), 2.0)                            # a dry flank

    def test_thermal_and_terraces(self):
        Z = np.zeros((40, 40)); Z[20:, :] = 200.0                          # a cliff
        T = TI.thermal(Z, 32, talus=35, iters=60)
        self.assertLess(float(TI.slope_deg(T, 32).max()), float(TI.slope_deg(Z, 32).max()) - 10)
        self.assertAlmostEqual(float(T.sum()), float(Z.sum()), delta=1e-6 * Z.sum())      # material moves, none is lost
        ramp = np.tile(np.linspace(0, 256, 200), (4, 1))
        S = TI.terraces(ramp, 64, 0.9)
        self.assertLess(float(np.abs(S - ramp).max()), 33)
        flat = np.abs(np.diff(S[0])) < 0.1 * (256 / 199.0)
        self.assertGreater(flat.mean(), 0.4)                               # most of it is bench
        np.testing.assert_array_equal(TI.terraces(ramp, 64, 0.9, weight=np.zeros_like(ramp)), ramp)

    def test_outcrops_only_on_steep_ground(self):
        f = TI.Field.from_fn(lambda X, Y: np.where(X > 0, X * 0.6, 0.0), (-2048, -2048, 2048, 2048), 32)
        X, Y = f.XY
        Z, rock = TI.outcrops(f.Z, 32, X, Y, height=30, seed=3)
        self.assertEqual(float(np.abs(Z - f.Z)[X < -200].max()), 0.0)
        self.assertGreater(float((Z - f.Z)[X > 200].max()), 5.0)
        self.assertTrue((rock >= 0).all() and (rock <= 1).all())

    def test_splat_and_density(self):
        E = self.info['eroded']
        S = TI.splat(E.Z, 32, rock=self.info['rock'], water_z=-10.0, XY=E.XY)
        for k in ('rock', 'mud', 'grass', 'trees', 'undergrowth', 'cavity'):
            self.assertEqual(S[k].shape, E.Z.shape); self.assertTrue((S[k] >= 0).all() and (S[k] <= 1).all(), k)
        self.assertTrue((S['rock'] + S['mud'] + S['grass'] >= 0.999).all())
        wet = S['acc'] > 60
        self.assertGreater(float(S['mud'][wet].mean()), float(S['mud'][~wet].mean()) + 0.2)
        cliff = np.zeros((40, 40)); cliff[20:, :] = 400.0
        self.assertGreater(float(TI.splat(cliff, 32)['rock'][19:21].min()), 0.9)
        dens = E.like(np.where(E.XY[0] > 0, 1.0, 0.0))
        pts = TI.scatter_density(dens, spacing=64, seed=9)
        self.assertEqual(pts, TI.scatter_density(dens, spacing=64, seed=9))
        self.assertTrue(all(x > -40 for x, y in pts))
        self.assertAlmostEqual(len(pts), 16 * 24, delta=40)                # the east half, one per 64 x 64
        self.assertEqual(len(TI.scatter_density(dens, spacing=64, seed=9, limit=50)), 50)

    def test_run_detail_files(self):
        d = tempfile.mkdtemp()
        try:
            h = os.path.join(d, 'height.png'); self.f.save(h)
            TI.save8(os.path.join(d, 'protect.png'), self.hard)
            rep = TI.run_detail(h, os.path.join(d, 'out'), os.path.join(d, 'protect.png'), 4, self.recipe, log=lambda *a: None)
            self.assertEqual(rep['max_change_in_protected_after_png'], 0.0)
            self.assertLess(rep['png_roundtrip_error'], 0.01)
            for n in ('detail.png', 'detail.png.json', 'eroded.png', 'hillshade_before.png', 'hillshade_after.png', 'hillshade_after_masks.png',
                      'splat_rock.png', 'splat_mud.png', 'splat_grass.png', 'splat_cavity.png', 'density_trees.png', 'density_undergrowth.png', 'report.json'):
                self.assertTrue(os.path.isfile(os.path.join(d, 'out', n)), n)
            with Image.open(os.path.join(d, 'out', 'hillshade_after.png')) as im: self.assertEqual(im.size, (65, 49))
            self.assertEqual(TI.load_mask(os.path.join(d, 'out', 'splat_rock.png'), self.f).shape, self.f.Z.shape)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class Reference(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp()
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)

    def _facade(self):
        """a plaster wall, 3 floors x 4 dark windows"""
        im = Image.new('RGB', (400, 300), (200, 180, 150))
        px = im.load()
        for fl in range(3):
            for c in range(4):
                for y in range(30 + fl * 90, 80 + fl * 90):
                    for x in range(40 + c * 90, 80 + c * 90): px[x, y] = (30 + (x * 7 + y * 3) % 30, 35, 45)
        p = os.path.join(self.d, 'f.png'); im.save(p); return p

    def test_facade(self):
        r = refimg.facade(self._facade(), os.path.join(self.d, 'o'), real_width=512)
        self.assertEqual(r['estimated_floors'], 3); self.assertEqual(r['estimated_columns'], 4)
        self.assertEqual(r['estimated_height'], 384.0); self.assertTrue(r['needs_visual_review'])
        self.assertEqual(r['palette'][0]['color'], '#c8b496')
        with Image.open(r['wall_crop']) as c: self.assertLess(float(np.asarray(c, float).std(axis=(0, 1)).max()), 2.0)      # bare wall, no window in it
        with open(os.path.join(self.d, 'o', 'facade.json')) as f: self.assertEqual(json.load(f)['estimated_floors'], 3)
        with self.assertRaises(ValueError): refimg.facade(os.path.join(self.d, 'missing.png'), self.d)

    def test_rectify(self):
        im = Image.new('RGB', (200, 200), (0, 0, 0))
        from PIL import ImageDraw
        quad = [(40, 30), (170, 50), (160, 180), (30, 150)]
        ImageDraw.Draw(im).polygon(quad, fill=(250, 250, 250))
        out = refimg.rectify(im, quad)
        a = np.asarray(out, float)[4:-4, 4:-4]
        self.assertGreater(float(a.mean()), 245)                           # the skewed white panel fills the frame
        with self.assertRaises(ValueError): refimg.rectify(im, [(40, 30), (30, 150), (160, 180), (170, 50)])     # wrong order
        with self.assertRaises(ValueError): refimg.rectify(im, [(0, 0), (500, 0), (500, 500), (0, 500)])

    def test_sheets_and_plan(self):
        a = self._facade(); b = os.path.join(self.d, 'b.png'); Image.new('RGB', (640, 360), (10, 90, 40)).save(b)
        r = refimg.compare(a, b, os.path.join(self.d, 'c.png'))
        with Image.open(r['comparison']) as im: self.assertEqual(im.height, 360 + 32)
        r = refimg.pairs([(a, b), (a, b)], os.path.join(self.d, 'p.png'))
        self.assertEqual(r['pairs'], 2)
        with self.assertRaises(ValueError): refimg.pairs([], os.path.join(self.d, 'p.png'))
        f = TI.Field.from_fn(hillside, B, 32)
        r = refimg.plan(f, os.path.join(self.d, 'plan.png'), image=b, marks=[('A', 0, 0, 90), ('B', 500, 500)], points=[(100, 100)], size=800)
        self.assertEqual(r['size'], [800, 600]); self.assertAlmostEqual(r['units_per_px'], 2.56)
        with Image.open(r['plan']) as im:
            self.assertEqual(im.size, (800, 600))
            self.assertEqual(im.getpixel((400 - 6, 300))[0], 255)          # the mark ring at the map centre


if __name__ == '__main__':
    unittest.main()
