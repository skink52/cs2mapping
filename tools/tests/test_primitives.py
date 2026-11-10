"""create/primitives.py: closed outward solids, FGD-checked entities, I/O wiring, and a written map that passes create/check_mesh.py.

  python -m unittest discover -s tools/tests -p "test_primitives.py" -v
"""
import math, os, shutil, subprocess, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F

sys.path.append(F.CREATE)          # appended: tools/dmx.py stays first for vmapedit; primitives' shape code imports no dmx
import primitives as P


class Shapes(unittest.TestCase):
    def solid(self, shape, vol=None, tol=1e-6):
        self.assertEqual(P.check(shape), [])
        if vol is not None: self.assertAlmostEqual(P.volume(shape), vol, delta=max(tol, abs(vol) * tol))
        for f in shape[1]:                                   # first corner convex: vmaplib's face normal must agree with Newell's
            v = shape[0]; a, b, c = v[f[0]], v[f[1]], v[f[2]]
            n3 = P._cross(P._sub(b, a), P._sub(c, a))
            self.assertGreater(P._dot(n3, P.newell(v, f)), 0)

    def test_box_wedge_prism_cylinder(self):
        self.solid(P.box((0, 0, 0), (64, 32, 16)), 64 * 32 * 16)
        for rise in ('+x', '-x', '+y', '-y'):
            self.solid(P.wedge((0, 0, 0), (128, 64, 32), rise), 128 * 64 * 32 / 2)
        self.solid(P.prism([(0, 0), (100, 0), (100, 30), (30, 30), (30, 100), (0, 100)], 0, 50), (100 * 30 + 30 * 70) * 50)   # L shape
        self.solid(P.prism([(0, 0), (0, 10), (10, 10), (10, 0)], 0, 1), 100)                                                  # clockwise input
        n = 12
        self.solid(P.cylinder((0, 0), 32, 0, 64, n), 0.5 * n * 32 * 32 * math.sin(2 * math.pi / n) * 64)

    def test_stairs(self):
        s = P.stairs((0, 0, 0), (128, 64, 64), 8, '+x', tread_mat='materials/t.vmat')
        self.solid(s, sum(i * 8 * 16 * 64 for i in range(1, 9)))
        top = [i for i, f in enumerate(s[1]) if P._unit(P.newell(s[0], f))[2] > 0.99]
        self.assertEqual(len(top), 8)
        self.assertTrue(all(s[2][i] == 'materials/t.vmat' for i in top))
        self.solid(P.stairs((0, 0, 0), (64, 128, 64), 4, '-y'))

    def test_arch_revolve_sweep_extrude(self):
        r_in, r_out, spring, depth = 48.0, 64.0, 80.0, 16.0
        a = P.arch((0, 0, 0), 2 * r_in, spring + r_in, depth, r_out - r_in, 64)
        legs = 2 * (r_out - r_in) * spring
        self.solid(a, (legs + math.pi / 2 * (r_out ** 2 - r_in ** 2)) * depth, tol=0.01)
        self.solid(P.arch((0, 0, 0), 96, 48, 16, 16, 10, axis='y'))
        col = P.revolve([(0, 0), (12, 0), (10, 8), (8, 120), (12, 128), (0, 128)], 16)
        self.solid(col)
        self.solid(P.revolve([(20, 0), (10, 50)], 8))         # open ends get caps
        self.solid(P.sweep([(0, 0, 0), (100, 0, 0), (100, 100, 0)], P.rect(8, 8)), 200 * 64)
        self.solid(P.sweep([(0, 0, 0), (100, 0, 0), (100, 100, 0), (0, 100, 0)], P.circle(4, 6), closed=True))
        self.solid(P.extrude([(0, 0), (50, 0), (25, 40)], 10, 'yz'), 1000 * 10)

    def test_edits(self):
        s = P.merge(P.box((0, 0, 0), (8, 8, 8)), P.translate(P.box((0, 0, 0), (8, 8, 8)), (100, 0, 0)))
        self.solid(s, 1024)
        r = P.rotate_z(P.box((0, 0, 0), (10, 20, 5)), 90)
        self.solid(r, 1000)
        xs = [p[0] for p in r[0]]
        self.assertAlmostEqual(min(xs), -20, places=6)
        m = P.materials(P.box((0, 0, 0), (8, 8, 8)), lambda i, n: 'top.vmat' if n[2] > 0.5 else None)
        self.assertEqual(m[2].count('top.vmat'), 1)

    def test_check_catches_bad_meshes(self):
        v, f, m = P.box((0, 0, 0), (8, 8, 8))
        self.assertTrue(any('open edges' in x for x in P.check((v, f[:-1], m[:-1]))))
        flipped = (v, [x[::-1] for x in f], m)
        self.assertIn('faces wind inward (negative volume)', P.check(flipped))
        bad = (v, [f[0][::-1]] + f[1:], m)
        self.assertTrue(any('used twice' in x for x in P.check(bad)))
        with self.assertRaises(ValueError): P.stairs((0, 0, 0), (1, 1, 1), 0)
        with self.assertRaises(ValueError): P.arch((0, 0, 0), 100, 10, 8)


class Entities(unittest.TestCase):
    """entity() / connect() checks against the catalog, on an in-memory vmaplib (no map file)"""
    @classmethod
    def setUpClass(cls):
        P.CATALOG = F.catalog()
        # vmaplib needs create/dmx.py under the name dmx, while vmapedit (other tests) holds tools/dmx.py there: import vmaplib with
        # create/ first, then put the tools module back. vmaplib keeps its own references; primitives takes the types from vmaplib.
        saved = sys.modules.pop('dmx', None)
        sys.path.insert(0, F.CREATE)
        try:
            import vmaplib
            vmaplib.init(type('D', (), {'root': None})(), F.CREATE)
        finally:
            sys.path.remove(F.CREATE)
            sys.modules.pop('dmx', None)
            if saved is not None: sys.modules['dmx'] = saved
        cls.vmaplib = vmaplib

    def test_defaults_and_strict(self):
        e = P.entity('prop_dynamic', (1, 2, 3), model='models/x.vmdl')
        props = {a[0]: a[2] for a in e.get('entity_properties').attrs}
        self.assertEqual(props['solid'], '6'); self.assertEqual(props['model'], 'models/x.vmdl')
        with self.assertRaises(ValueError): P.entity('prop_dynamik', (0, 0, 0))
        with self.assertRaises(ValueError): P.entity('prop_dynamic', (0, 0, 0), bogus='1')

    def test_connect(self):
        r = P.entity('logic_relay', (0, 0, 0), targetname='r')
        P.connect(r, 'OnTrigger', 'r', 'CancelPending', delay=1.5)
        c = r.get('connectionsData')[0]
        self.assertEqual(c.get('outputName'), 'OnTrigger'); self.assertEqual(c.get('delay'), 1.5)
        with self.assertRaises(ValueError): P.connect(r, 'OnNothing', 'r', 'Trigger')


class WrittenMap(unittest.TestCase):
    """the fixture map (primitives on box_template.vmap) loads with tools/vmapedit and every mesh passes create/check_mesh.py"""
    @classmethod
    def setUpClass(cls):
        cls.root, cls.vmap = F.temp_root()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_meshes_valid(self):
        r = subprocess.run([sys.executable, os.path.join(F.CREATE, 'check_mesh.py'), self.vmap], capture_output=True, text=True, cwd=F.CREATE)
        self.assertEqual(r.returncode, 0, r.stderr)
        last = r.stdout.strip().splitlines()[-1]
        self.assertTrue(last.endswith(' 0 bad'), last)
        self.assertIn(' 6 meshes', last)                 # floor, slab, stairs, column, trigger box + the template's box ... see below

    def test_entities_and_brush_child(self):
        import vmapedit as V
        m = V.Map(self.vmap)
        classes = sorted(m.cls(e) for e in m.entities())
        self.assertEqual(classes.count('info_player_terrorist'), 3)
        trig = m.by_class('trigger_multiple')[0]
        kids = [c for c in m.children(trig) if m.type(c) == b'CMapMesh']
        self.assertEqual(len(kids), 1)
        lo, hi = m.bounds(trig)
        self.assertEqual([round(x) for x in lo], [10, 10, 0]); self.assertEqual([round(x) for x in hi], [60, 60, 72])
        self.assertEqual(m.P(trig, 'spawnflags'), '1')       # FGD default filled in
        conns = [m.conn_tuple(c)[:3] for c in m.conns(trig)]
        self.assertIn(('OnTrigger', 'relay1', 'Trigger'), conns)


if __name__ == '__main__':
    unittest.main()
