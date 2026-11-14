"""tools/watervol.py split_volumes: func_water meshes over 384 u cut into closed pieces no wider than 384 u (CS2 gives bigger ones no
physics hull; docs/reference/cs2-gotchas.md). Built on tools/box_template.vmap, no map content.

  python -m unittest discover -s tools/tests -p "test_watersplit.py" -v
"""
import os, sys, unittest
import numpy as np
TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import dmx, vmapedit as V, watervol as W, splitfaces as SF


class Ctx:
    def __init__(s): s.log, s.todo = [], []


def volume(m, node):
    polys, _ = SF.mesh_read(m, node)
    v = 0.0
    for p in polys:
        Q = [c['pos'] for c in p['corners']]
        for i in range(1, len(Q) - 1): v += np.dot(Q[0], np.cross(Q[i], Q[i + 1])) / 6
    return abs(v)


def water_map(mn, mx):
    m = V.Map(W.TEMPLATE)
    tm = V.Map(W.TEMPLATE); tnode = tm.children(tm.world)[0]
    e = m.new_entity('func_water', [0, 0, 0], {})
    j = W.box(m, tm, tnode, mn, mx, b'materials/anubis/anubis_water_canal.vmat')
    dmx.geta(m.E[e], b'children')[2].append(j)
    return m, e


def meshes(m, e): return [n for n in m.children(e) if m.type(n) == b'CMapMesh']


class SplitVolumes(unittest.TestCase):
    def test_long_box_cut_into_closed_pieces(self):
        m, e = water_map([0, 0, -100], [1000, 600, 0])
        before = volume(m, meshes(m, e)[0])
        c = Ctx()
        self.assertEqual(W.split_volumes(m, c), 1)
        ms = meshes(m, e)
        self.assertEqual(len(ms), 3 * 2)
        for n in ms:
            lo, hi = m.bounds(n)
            self.assertLessEqual(max(hi[0] - lo[0], hi[1] - lo[1]), W.CELL + 1e-3)
            self.assertNotIn(-1, m.g(m.g(n, b'meshData'), b'edgeFaceIndices'))      # closed
            self.assertEqual(SF.mesh_check(m, n), [])
        self.assertAlmostEqual(sum(volume(m, n) for n in ms), before, delta=1e-3 * before)
        # every face of the test box is water; the cut faces are new nodraw caps: 2 or 3 per piece on a 3 x 2 grid, 7 in all
        caps = []
        for n in ms:
            polys, mats = SF.mesh_read(m, n)
            caps.append(sum(1 for p in polys if mats[p['attrs']['materialindex:0']] == W.NODRAW))
            self.assertEqual(len(polys), 6)                                           # each piece is a box
        self.assertEqual(sorted(caps), [2, 2, 2, 2, 3, 3])

    def test_small_box_untouched_and_rerun_is_a_no_op(self):
        m, e = water_map([0, 0, -100], [384, 300, 0])
        self.assertEqual(W.split_volumes(m, Ctx()), 0)
        m, e = water_map([0, 0, -100], [800, 300, 0])
        W.split_volumes(m, Ctx())
        n = len(meshes(m, e))
        self.assertEqual(W.split_volumes(m, Ctx()), 0)
        self.assertEqual(len(meshes(m, e)), n)

    def _subdivide(self, m, n, disp=0.0):
        """give the mesh subdivision data the way the importer writes a CS:GO displacement (levels on the top's half-edges, 17 x 17 streams)"""
        sd = m.g(m.g(n, b'meshData'), b'subdivisionData')
        lv = dmx.geta(m.E[sd], b'subdivisionLevels'); lv[2] = [5 if i % 6 == 0 else 0 for i in range(len(lv[2]))]
        st = m.new_el(b'DmeVertexDataStream', [[b'name', dmx.T_STR, b'displacement:0'], [b'semanticName', dmx.T_STR, b'displacement'],
                                                [b'semanticIndex', dmx.T_INT, 0], [b'vertexBufferLocation', dmx.T_INT, 0],
                                                [b'dataStateFlags', dmx.T_INT, 0], [b'subdivisionBinding', dmx.T_ELEM, -1],
                                                [b'data', dmx.ARR + dmx.T_V3, [[0.0, 0.0, disp]] * 289]], name=b'displacement:0')
        dmx.geta(m.E[sd], b'streams')[2].append(st)

    def test_flat_displaced_top_dropped_then_cut(self):
        # ba_jail_seaside's sea, ba_jail_keimusho's pools: a subdivision mesh whose displacement is all zero. CS2 gives a subdivided
        # func_water mesh no hull at any size (a 104 x 299 one failed), so the subdivision is dropped and the plain box cut as usual
        m, e = water_map([0, 0, -100], [1000, 600, 0])
        self._subdivide(m, meshes(m, e)[0])
        c = Ctx()
        self.assertEqual(W.split_volumes(m, c), 1)
        self.assertIn('subdivision dropped', c.log[0])
        for n in meshes(m, e):
            self.assertFalse(SF.mesh_has_subdivision(m, n))
            self.assertEqual(SF.mesh_check(m, n), [])
            sd = m.g(m.g(n, b'meshData'), b'subdivisionData')
            self.assertFalse(any(m.g(sd, b'subdivisionLevels')))
        self.assertEqual(len(meshes(m, e)), 6)

    def test_real_displacement_left_whole(self):
        m, e = water_map([0, 0, -100], [1000, 600, 0])
        n = meshes(m, e)[0]
        self._subdivide(m, n, disp=8.0)
        c = Ctx()
        self.assertEqual(W.split_volumes(m, c), 0)
        self.assertTrue(SF.mesh_has_subdivision(m, n))
        self.assertIn('real displacement', c.todo[0])

    def test_slanted_side_cut(self):
        # a convex footprint with a slanted side (ba_jail_seaside's sea is a hexagon): a cut plane that misses a piece needs no cap
        m, e = water_map([0, 0, -100], [1000, 1000, 0])
        n = meshes(m, e)[0]
        polys, _ = SF.mesh_read(m, n)
        tmpl = polys[0]
        foot = [(0, 0), (1000, 0), (1000, 600), (600, 1000), (0, 1000)]                # counter-clockwise from above

        def face(pts, nrm):
            return {'attrs': dict(tmpl['attrs']), 'corners': [{'pos': np.array(q, float), 'fvd': {k: (np.array(nrm, float) if k.startswith('normal')
                    else v.copy()) for k, v in tmpl['corners'][0]['fvd'].items()}} for q in pts]}
        prism = [face([(x, y, 0) for x, y in foot], (0, 0, 1)), face([(x, y, -100) for x, y in foot[::-1]], (0, 0, -1))]
        for i in range(len(foot)):
            (x0, y0), (x1, y1) = foot[i], foot[(i + 1) % len(foot)]
            nrm = np.array([y1 - y0, x0 - x1, 0.0]); nrm /= np.linalg.norm(nrm)
            prism.append(face([(x0, y0, -100), (x1, y1, -100), (x1, y1, 0), (x0, y0, 0)], nrm))
        self.assertIsNone(SF.mesh_write(m, n, prism))
        before = volume(m, n)
        self.assertEqual(W.split_volumes(m, Ctx()), 1)
        ms = meshes(m, e)
        self.assertEqual(len(ms), 9)                                                   # 3 x 3 cells, all reached by the footprint
        for x in ms:
            self.assertNotIn(-1, m.g(m.g(x, b'meshData'), b'edgeFaceIndices'))
            self.assertEqual(SF.mesh_check(m, x), [])
        self.assertAlmostEqual(sum(volume(m, x) for x in ms), before, delta=1e-3 * before)

if __name__ == '__main__':
    unittest.main()
