"""D2 spotbeam.py: beam_spotlight (kept by the importer, draws nothing) -> the point_spotlight beam cone; rotating ones get a
func_rotating <name>_rot that the beam is SetParent to at spawn.

  python -m unittest discover -s tools/tests -p "test_borrowed_d2.py" -v
"""
import os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vmapedit as V, watervol, spotbeam, dmx

VMF = ('world\n{\n"classname" "worldspawn"\n}\n'
       'entity\n{\n"classname" "beam_spotlight"\n"origin" "0 0 0"\n"angles" "-90 0 0"\n"spawnflags" "1"\n"spotlightlength" "300"\n'
       '"spotlightwidth" "20"\n"rendercolor" "94 241 67"\n"HDRColorScale" "0.7"\n"maxspeed" "100"\n}\n'
       'entity\n{\n"classname" "beam_spotlight"\n"targetname" "disco"\n"origin" "500 0 0"\n"angles" "0 0 0"\n"spawnflags" "29"\n'
       '"maxspeed" "60"\n}\n'
       'entity\n{\n"classname" "point_spotlight"\n"origin" "0 500 0"\n"angles" "90 0 0"\n}\n')


class Ctx:
    def __init__(s): s.log = []; s.todo = []; s.files = {}
    def write(s, rel, data): s.files[rel] = data if isinstance(data, bytes) else data.encode()


class BeamSpotlight(unittest.TestCase):
    def setUp(s):
        s.tmp = tempfile.mkdtemp(); s.vmf = os.path.join(s.tmp, 'm.vmf')
        with open(s.vmf, 'w') as fh: fh.write(VMF)
        m = V.Map(watervol.TEMPLATE); dmx.geta(m.E[m.world], b'children')[2] = []
        m.new_entity('beam_spotlight', [0, 0, 0], {'spawnflags': '1'}, angles=(-90, 0, 0))
        m.new_entity('beam_spotlight', [500, 0, 0], {'targetname': 'disco', 'spawnflags': '29'})
        r = m.new_entity('logic_relay', [0, 0, 0], {'targetname': 'r'})
        m.add_conn(r, 'OnTrigger', 'disco', 'Stop'); m.add_conn(r, 'OnTrigger', 'disco', 'LightOff')
        s.m = m; s.relay = r

    def tearDown(s): shutil.rmtree(s.tmp, ignore_errors=True)

    def test_from_vmf(s):
        sp = spotbeam.from_vmf(s.vmf)
        s.assertEqual(sorted(x['classname'] for x in sp), ['beam_spotlight', 'beam_spotlight', 'point_spotlight'])
        s.assertEqual(sp[0]['hdrcolorscale'], '0.7')

    def test_convert(s):
        c = Ctx(); m = s.m
        spotbeam.run(m, c, spotbeam.from_vmf(s.vmf))
        s.assertEqual(m.by_class('beam_spotlight'), [])                   # the importer's copies are replaced
        fb = m.by_class('func_brush'); s.assertEqual(len(fb), 3)
        mids = sorted(tuple(round(x) for x in m.origin(e)) for e in fb)
        s.assertIn((0, 0, 150), mids)                                     # pitch -90 = straight up, half of 300
        s.assertIn((500 + 250, 0, 0), mids)                               # default length 500 along +x
        rot = m.by_class('func_rotating'); s.assertEqual(len(rot), 1)
        s.assertEqual(m.name(rot[0]), 'disco_rot')
        s.assertEqual(m.P(rot[0], 'spawnflags'), str(64 | 1 | 2 | 4))     # start on, reverse (8), X axis (16) -> 1, 2, 4; never solid
        s.assertEqual(m.P(rot[0], 'maxspeed'), '60')
        la = [e for e in m.by_class('logic_auto') if m.name(e) == 'port_logic_auto']; s.assertEqual(len(la), 1)
        cs = {m.conn_tuple(cn)[:4] for cn in m.conns(la[0])}
        s.assertIn(('OnMapSpawn', 'disco', 'SetParent', 'disco_rot'), cs); s.assertIn(('OnMultiNewRound', 'disco', 'SetParent', 'disco_rot'), cs)
        rc = {m.conn_tuple(cn)[1:3] for cn in m.conns(s.relay)}
        s.assertIn(('disco_rot', 'Stop'), rc); s.assertIn(('disco', 'Disable'), rc)
        disco = [e for e in fb if m.name(e) == 'disco'][0]
        s.assertEqual(m.P(disco, 'StartDisabled'), '0'); s.assertFalse(m.P(disco, 'parentname'))
        s.assertTrue(any(k.endswith('.vmat') for k in c.files))
        s.assertTrue(any('beam_spotlight: 2 beams' in l for l in c.log)); s.assertTrue(any('point_spotlight: 1' in l for l in c.log))
        s.assertTrue(any('dynamic light' in t for t in c.todo))          # first one has no spawnflags 2

    def test_rerun_adds_nothing(s):
        c = Ctx(); m = s.m; sp = spotbeam.from_vmf(s.vmf)
        spotbeam.run(m, c, sp); n = len(m.by_class('func_brush')), len(m.by_class('func_rotating'))
        spotbeam.run(m, Ctx(), sp)
        s.assertEqual((len(m.by_class('func_brush')), len(m.by_class('func_rotating'))), n)

    def test_kept_without_vmf(s):
        sp = spotbeam.kept(s.m)
        s.assertEqual(len(sp), 2); s.assertEqual(sp[1]['targetname'], 'disco')
        c = Ctx(); spotbeam.run(s.m, c, sp)
        s.assertEqual(len(s.m.by_class('func_brush')), 2); s.assertEqual(len(s.m.by_class('func_rotating')), 1)

    def test_rot_flags(s):
        s.assertEqual(spotbeam._rot_flags(1), 64); s.assertEqual(spotbeam._rot_flags(4 | 32), 64 | 1 | 8)


if __name__ == '__main__':
    unittest.main()
