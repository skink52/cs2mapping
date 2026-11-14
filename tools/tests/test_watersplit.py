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


if __name__ == '__main__':
    unittest.main()
