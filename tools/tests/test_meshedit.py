"""create/meshedit.py: face ops, deformers, bevel, CSG, UV / paint writing (the written map passes create/check_mesh.py).

  python -m unittest discover -s tools/tests -p "test_meshedit.py" -v
"""
import math, os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
sys.path.append(F.CREATE)
import primitives as P
import meshedit as M

B = P.box((0, 0, 0), (64, 64, 64))


class Ops(unittest.TestCase):
    def ok(self, s, vol=None, tol=1e-6):
        self.assertEqual(P.check(s), [])
        if vol is not None: self.assertAlmostEqual(P.volume(s), vol, delta=abs(vol) * tol + 1e-6)
        return s

    def test_select(self):
        self.assertEqual(len(M.select(B, (0, 0, 1))), 1)
        self.assertEqual(len(M.select(B, box=((-1, -1, 30), (65, 65, 34)))), 4)

    def test_extrude_inset_move(self):
        self.ok(M.extrude(B, M.select(B, (0, 0, 1)), 32), 64 * 64 * 96)
        s = self.ok(M.inset(B, M.select(B, (0, 0, 1)), 8), 64 ** 3)
        inner = [i for i in M.select(s, (0, 0, 1)) if all(5 <= s[0][v][0] <= 59 for v in s[1][i])]
        self.assertEqual(len(inner), 1)
        self.ok(M.extrude(s, inner, -16))                                            # a recess in the top
        self.ok(M.move(B, M.select(B, (0, 0, 1)), (0, 0, 16)), 64 * 64 * 80)

    def test_deformers(self):
        col = M.subdivide(P.box((0, 0, 0), (32, 32, 256)), 2)
        self.ok(col, 32 * 32 * 256)
        t = self.ok(M.twist(col, 90))
        top = [p for p in t[0] if p[2] > 255]
        self.assertTrue(any(abs(p[0] - 32) < 1e-6 and abs(p[1]) < 1e-6 for p in top))   # corner (0,0) turned 90 degrees about the centre
        self.ok(M.taper(B, 0.5), 64 * (64 * 64 + 32 * 32 + 64 * 32) / 3)              # frustum
        bent = self.ok(M.bend(M.subdivide(P.box((0, 0, 0), (16, 16, 256)), 4), 90))
        self.assertGreater(max(p[0] for p in bent[0]), 100)                            # the top swung toward +x
        self.ok(M.noise(M.subdivide(B, 3), 4))
        sm = self.ok(M.smooth(M.subdivide(B, 2), 2))
        self.assertLess(P.volume(sm), 64 ** 3)
        self.ok(M.mirror(P.box((10, 0, 0), (20, 10, 10)), 'x'), 2000)
        self.ok(M.subdivide(P.wedge((0, 0, 0), (64, 64, 64)), 3), 64 ** 3 / 2)

    def test_bevel(self):
        ch = self.ok(M.bevel(B, 8))
        r = 8; k = 0                                                                 # 12 edges, 90 degrees: chamfer tangent to radius 8
        self.assertLess(P.volume(ch), 64 ** 3); self.assertGreater(P.volume(ch), 64 ** 3 - 12 * 64 * r * r)
        self.assertEqual(len(ch[1]), 6 + 12)                                         # faces + edge strips (equal chamfers meet in a point)
        rnd = self.ok(M.bevel(B, 8, 3))
        self.assertLess(P.volume(rnd), P.volume(ch))                                # more tangent planes (the 45 degree one included)
        only_top = self.ok(M.bevel(B, 8, edges=lambda a, b: a[2] > 63 and b[2] > 63))
        self.assertEqual(len(only_top[1]), 6 + 4 + 0)
        with self.assertRaises(ValueError): M.bevel(P.stairs((0, 0, 0), (64, 64, 64), 4), 4)

    def test_csg(self):
        self.ok(M.subtract(B, P.box((16, -10, 16), (48, 74, 48))), 64 ** 3 - 32 * 32 * 64)      # a tunnel through
        self.ok(M.union(B, P.box((32, 32, 32), (96, 96, 96))), 2 * 64 ** 3 - 32 ** 3)
        self.ok(M.intersect(B, P.box((32, 32, 32), (96, 96, 96))), 32 ** 3)
        door = self.ok(M.subtract(P.box((0, 0, 0), (256, 16, 128)), P.box((96, -8, 0), (160, 24, 96), 'materials/frame.vmat')), 256 * 16 * 128 - 64 * 16 * 96)
        self.assertIn('materials/frame.vmat', door[2])                               # the cut's faces take the cutter's material
        n = 16
        self.ok(M.cut(P.box((-64, -64, 0), (64, 64, 32)), P.cylinder((0, 0), 24, -8, 40, n)), 128 * 128 * 32 - 0.5 * n * 24 * 24 * math.sin(2 * math.pi / n) * 32)

    def test_uv_math(self):
        s = P.box((0, 0, 0), (128, 64, 32))
        top = M.select(s, (0, 0, 1))[0]
        u, v, sc, sh, c = M.face_uvs(s, top, M.uv(fit=(1, 1)), (512, 512))
        us = [x for x, _ in c]; vs = [y for _, y in c]
        self.assertAlmostEqual(min(us), 0.0); self.assertAlmostEqual(max(us), 1.0)
        self.assertAlmostEqual(min(vs), 0.0); self.assertAlmostEqual(max(vs), 1.0)
        u2, v2, *_ = M.face_uvs(s, top, M.uv(rotate=90))
        self.assertAlmostEqual(abs(u2[1]), 1.0, places=6)                           # Hammer's top axes (1,0,0) / (0,-1,0) turned 90 degrees


BUILD = r'''
import os, sys
sys.path.insert(0, CREATE)
import vmapgen, primitives as P, meshedit as M
d = vmapgen.open_map(os.path.join(TOOLS, 'box_template.vmap'), os.path.dirname(OUT))
wall = M.subtract(P.box((0, 0, 0), (256, 16, 128)), P.box((96, -8, 0), (160, 24, 96)))
M.write(wall, uv_specs={i: M.uv(scale=0.5, rotate=15) for i in range(len(wall[1]))}, group='t')
M.write(M.bevel(P.box((300, 0, 0), (364, 64, 64)), 8, 2), group='t')
M.write(M.subdivide(P.box((400, 0, 0), (528, 128, 8), 'materials/blend.vmat'), 4), paint=lambda p: (p[0] - 400) / 128.0,
        tint=lambda p: (255, 200, 200, 255), group='t')
M.write(M.twist(M.subdivide(P.box((600, 0, 0), (632, 32, 256)), 3), 45), group='t')
vmapgen.finish(d, OUT, group='t')
'''


class Written(unittest.TestCase):
    def test_map_meshes_valid(self):
        root = tempfile.mkdtemp(prefix='cs2mcp_me_')
        try:
            out = F.make_map(os.path.join(root, 'me.vmap'), BUILD)
            r = subprocess.run([sys.executable, os.path.join(F.CREATE, 'check_mesh.py'), out], capture_output=True, text=True, cwd=F.CREATE)
            last = r.stdout.strip().splitlines()[-1]
            self.assertTrue(last.endswith(' 5 meshes 0 bad'), r.stdout + r.stderr)    # 4 + the template's own box
            import vmapedit as V
            m = V.Map(out)
            names = []
            for n, _ in m.walk():
                if m.type(n) != b'CMapMesh': continue
                md = m.g(n, b'meshData')
                names.append(sorted(m.E[st]['name'].decode() for st in m.g(m.g(md, b'faceVertexData'), b'streams')))
            self.assertTrue(any('VertexPaintBlendParams:0' in s for s in names))
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
