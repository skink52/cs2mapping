"""B7 momentum.py: Momentum Mod triggers -> trigger_teleport / trigger_multiple + io script inputs; the script section patch.

  python -m unittest discover -s tools/tests -p "test_borrowed_b7.py" -v
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vmapedit as V, watervol, momentum, gen_script, dmx


class Ctx:
    def __init__(s): s.log = []; s.todo = []; s.script = 'mom_io_script'


class Momentum(unittest.TestCase):
    def setUp(self):
        m = V.Map(watervol.TEMPLATE); dmx.geta(m.E[m.world], b'children')[2] = []
        self.tp_plain = m.new_entity('trigger_momentum_teleport', [0, 0, 0], {'target': 'd1', 'stop': '1', 'resetang': '1'})
        self.tp_keep = m.new_entity('trigger_momentum_teleport', [0, 0, 0], {'targetname': 'keepspeed', 'target': 'd2', 'stop': '0', 'resetang': '1'})
        self.speed = m.new_entity('trigger_momentum_speedthreshold', [0, 0, 0], {'AboveOrBelow': '0', 'Horizontal': '1', 'HorizontalSpeed': '500'})
        m.add_conn(self.speed, 'OnThreshold', 'door', 'Open')
        self.slide = m.new_entity('trigger_momentum_slide', [0, 0, 0], {})
        self.push = m.new_entity('trigger_momentum_push', [0, 0, 0], {'pushdir': '0 90 0', 'force': '400', 'increase': '1', 'spawnflags': str(momentum.PUSH_ON_START | momentum.PUSH_ON_END)})
        self.m = m

    def test_convert(self):
        c = Ctx(); m = self.m
        self.assertEqual(momentum.run(m, c), 5)
        self.assertEqual(m.cls(self.tp_plain), 'trigger_teleport'); self.assertEqual(m.P(self.tp_plain, 'target'), 'd1')
        self.assertEqual(m.cls(self.tp_keep), 'trigger_multiple'); self.assertIsNone(m.P(self.tp_keep, 'target'))
        self.assertEqual(c.momentum['teleport'], [{'target': 'd2', 'stop': False, 'resetang': True}])
        outs = lambda e: sorted((t[0], t[1], t[2], t[3]) for t in (m.conn_tuple(cc) for cc in m.conns(e)))
        self.assertIn(('OnUser1', 'door', 'Open', ''), outs(self.speed))
        self.assertIn(('OnStartTouch', 'mom_io_script', 'RunScriptInput', 'MomSpeedIn_0'), outs(self.speed))
        self.assertEqual([o[3] for o in outs(self.push)], ['MomPush_0', 'MomPush_0'])
        vec = c.momentum['push'][0]['vec']
        self.assertAlmostEqual(vec[1], 400.0); self.assertAlmostEqual(vec[0], 0.0, 3); self.assertEqual(c.momentum['push'][0]['mode'], 1)
        self.assertTrue(c.momentum['slide'])
        self.assertIsNone(m.P(self.speed, 'HorizontalSpeed'))

    def test_push_modes(self):
        p = momentum.push_entry({'pushdir': '-90 0 0', 'force': '300'})       # defaults: on end touch, add if slower
        self.assertEqual((p['mode'], p['start'], p['end']), (3, False, True)); self.assertAlmostEqual(p['vec'][2], 300.0)
        q = momentum.push_entry({'pushdir': '10 20 30', 'spawnflags': str(momentum.PUSH_DIR_AS_FORCE | momentum.PUSH_ON_START)})
        self.assertEqual(q['vec'], [10.0, 20.0, 30.0])

    def test_script_patch(self):
        c = Ctx(); momentum.run(self.m, c)
        base = gen_script.build('mom', c.script, None, None, None, None, {0.5}, None, None, None)
        js = momentum.patch_script(base, c.momentum)
        self.assertIn('const MOM = {', js); self.assertIn(momentum.HEAD_LINE, js)
        self.assertEqual(js.count('const THINKERS'), 1)
        for n in ('Entities', 'Console', 'CSPlayerController'): self.assertRegex(js.split('\n')[0], r'\b%s\b' % n)
        again = momentum.patch_script(js, c.momentum)              # rerun replaces the section
        self.assertEqual(again.count('Momentum Mod triggers (trigger_momentum_*'), 1)
        alone = momentum.patch_script('', c.momentum)
        self.assertIn('const THINKERS', alone); self.assertTrue(alone.startswith('import {'))


if __name__ == '__main__':
    unittest.main()
