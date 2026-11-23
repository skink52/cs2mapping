"""B2 / B3 (repair.py): thin boost / gravity triggers reported or raised (thintrig / thintrigfix), spawns in the floor reported or lifted
(spawnlift / spawnliftfix). Synthetic maps built from tools/box_template.vmap.

  python -m unittest discover -s tools/tests -p "test_borrowed_b2.py" -v
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vmapedit as V, watervol, repair, dmx


class Ctx:
    def __init__(s): s.log = []; s.todo = []


def blank():
    m = V.Map(watervol.TEMPLATE)
    tm = V.Map(watervol.TEMPLATE)
    kids = dmx.geta(m.E[m.world], b'children'); kids[2] = []
    return m, (lambda mn, mx, mat=b'materials/dev/floor.vmat', parent=None: _box(m, tm, mn, mx, mat, parent))


def _box(m, tm, mn, mx, mat, parent):
    j = watervol.box(m, tm, tm.children(tm.world)[0], mn, mx, mat)
    dmx.geta(m.E[parent if parent is not None else m.world], b'children')[2].append(j)
    return j


class ThinTriggers(unittest.TestCase):
    def setUp(self):
        self.m, self.box = blank()
        m = self.m
        self.push = m.new_entity('trigger_multiple', [0, 0, 0], {'targetname': 'pad'})
        m.add_conn(self.push, 'OnStartTouch', 'map_io_script', 'RunScriptInput', 'PushIn_3')
        self.box([0, 0, 0], [128, 128, 2], b'materials/tools/toolstrigger.vmat', self.push)
        boost = m.new_entity('trigger_once', [0, 0, 0], {})
        m.add_conn(boost, 'OnStartTouch', '!activator', 'AddOutput', 'basevelocity 0 0 900')
        self.box([300, 0, 0], [364, 64, 4], b'materials/tools/toolstrigger.vmat', boost)
        tall = m.new_entity('trigger_gravity', [0, 0, 0], {'gravity': '0.5'})
        self.box([600, 0, 0], [664, 64, 64], b'materials/tools/toolstrigger.vmat', tall)
        plain = m.new_entity('trigger_multiple', [0, 0, 0], {})     # not a boost: never reported
        self.box([900, 0, 0], [964, 64, 1], b'materials/tools/toolstrigger.vmat', plain)

    def test_report_only_by_default(self):
        c = Ctx()
        found = repair.thin_triggers(self.m, c)
        self.assertEqual(sorted(x[1] for x in found), ['basevelocity', 'push'])
        self.assertEqual(c.log, []); self.assertTrue(c.todo[0].startswith('thintrig: 2 '))
        self.assertAlmostEqual(self.m.bounds(self.push)[1][2], 2.0)     # nothing moved

    def test_fix_raises_top_only(self):
        c = Ctx()
        repair.thin_triggers(self.m, c, fix=True)
        lo, hi = self.m.bounds(self.push)
        self.assertAlmostEqual(lo[2], 0.0); self.assertAlmostEqual(hi[2], 6.0)
        self.assertTrue(c.log[0].startswith('thintrigfix: 2 '))
        self.assertEqual(repair.thin_triggers(self.m, Ctx()), [])     # rerun: nothing left


class SpawnLift(unittest.TestCase):
    def setUp(self):
        self.m, box = blank()
        box([-256, -256, -64], [256, 256, 0])                 # floor, top at z 0
        box([100, -64, 40], [228, 64, 48])                    # a low shelf 40 u over the floor
        m = self.m
        self.sunk = m.new_entity('info_player_terrorist', [0, 0, -3], {})
        self.ok = m.new_entity('info_player_terrorist', [-100, 0, 0.7], {})     # imported height: left alone
        self.boxed = m.new_entity('info_player_counterterrorist', [164, 0, 0], {})  # under the shelf: no room

    def test_report(self):
        c = Ctx()
        found = repair.spawn_lift(self.m, c)
        self.assertEqual(len(found), 2)
        self.assertTrue(c.todo[0].startswith('spawnlift: 2 ')); self.assertEqual(c.log, [])
        self.assertEqual(self.m.origin(self.sunk)[2], -3)

    def test_fix(self):
        c = Ctx()
        repair.spawn_lift(self.m, c, fix=True)
        self.assertAlmostEqual(self.m.origin(self.sunk)[2], 2.0)
        self.assertAlmostEqual(self.m.origin(self.ok)[2], 0.7)
        self.assertAlmostEqual(self.m.origin(self.boxed)[2], 0.0)
        self.assertTrue(c.log[0].startswith('spawnliftfix: 1 ')); self.assertTrue(c.todo[0].startswith('spawnliftfix: 1 '))


if __name__ == '__main__':
    unittest.main()
