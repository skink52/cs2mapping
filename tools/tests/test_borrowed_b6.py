"""B6 skysplit.py --bsp: nodes sorted by the BSP room of the sky_camera (room / shared / elsewhere), with the BSP reading stubbed.

  python -m unittest discover -s tools/tests -p "test_borrowed_b6.py" -v
"""
import os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vmapedit as V, watervol, skysplit as S, dmx

ROOM = [((0, 0, 0), (256, 256, 128))]                       # the skybox room's empty leaves
REST = [((1000, 0, 0), (2000, 1000, 300)), ((300, 0, 0), (900, 256, 128))]   # the play space


class BspRoom(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        m = V.Map(watervol.TEMPLATE); tm = V.Map(watervol.TEMPLATE)
        kids = dmx.geta(m.E[m.world], b'children'); kids[2] = []
        def box(mn, mx):
            j = watervol.box(m, tm, tm.children(tm.world)[0], mn, mx, b'materials/dev/x.vmat'); kids[2].append(j); return j
        self.floor = box([0, 0, -16], [256, 256, 0])           # skybox floor: room only
        self.wall = box([256, 0, 0], [300, 256, 128])          # wall between room and play space: shared
        self.play = box([1200, 0, 0], [1400, 200, 16])         # play space
        m.new_entity('sky_camera', [128, 128, 64], {'scale': '16'})
        self.spawn = m.new_entity('info_player_terrorist', [1300, 100, 32], {})
        self.src = os.path.join(self.tmp, 'm.vmap'); m.save(self.src)
        self._orig = S.bsp_room
        S.bsp_room = lambda path, cam: (ROOM, REST, {1}, lambda p: 1 if all(ROOM[0][0][k] <= p[k] <= ROOM[0][1][k] for k in range(3)) else 2)

    def tearDown(self):
        S.bsp_room = self._orig; shutil.rmtree(self.tmp, ignore_errors=True)

    def test_classify_and_split(self):
        m = V.Map(self.src)
        where, (lo, hi) = S.room_classifier(m, 'x.bsp', [128, 128, 64])
        got = {n: where(m, n) for n in m.children(m.world) if m.type(n) == b'CMapMesh'}
        self.assertEqual(sorted(got.values(), key=str), [None, 'both', 'room'])
        main, sky = os.path.join(self.tmp, 'main.vmap'), os.path.join(self.tmp, 'sky.vmap')
        msg = S.split(self.src, main, sky, 'm', bsp='x.bsp')
        self.assertIn('BSP room', msg)
        mm, ss = V.Map(main), V.Map(sky)
        count = lambda mp: sum(1 for n in mp.children(mp.world) if mp.type(n) == b'CMapMesh')
        self.assertEqual(count(mm), 2)                          # play box + shared wall stay
        self.assertEqual(count(ss), 2)                          # floor + a copy of the wall
        self.assertTrue(mm.by_class('skybox_reference')); self.assertFalse(mm.by_class('sky_camera'))

    def test_refuses_spawn_in_room(self):
        m = V.Map(self.src)
        m.new_entity('info_player_counterterrorist', [100, 100, 10], {})
        with self.assertRaises(SystemExit): S.room_classifier(m, 'x.bsp', [128, 128, 64])

    def test_not_a_bsp(self):
        p = os.path.join(self.tmp, 'no.bsp')
        with open(p, 'wb') as fh: fh.write(b'NOPE' + bytes(2000))
        with self.assertRaises(ValueError): self._orig(p, [0, 0, 0])


if __name__ == '__main__':
    unittest.main()
