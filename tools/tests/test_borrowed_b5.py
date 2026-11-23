"""B5 smokestack.py: env_smokestack / env_spritetrail kept by the importer and func_dustmotes from the VMF -> info_particle_system with
generated vpcf66 particles under particles/port_smoke/.

  python -m unittest discover -s tools/tests -p "test_borrowed_b5.py" -v
"""
import os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vmapedit as V, watervol, smokestack, kv3text, dmx

PLANES = ['(0 0 64) (0 128 64) (128 128 64)', '(0 128 0) (0 0 0) (128 0 0)', '(0 0 64) (0 0 0) (0 128 0)',
          '(128 128 64) (128 128 0) (128 0 0)', '(128 0 64) (128 0 0) (0 0 0)', '(0 128 64) (0 128 0) (128 128 0)']
VMF = ('world\n{\n"classname" "worldspawn"\n}\nentity\n{\n"classname" "func_dustmotes"\n"targetname" "motes"\n"SpawnRate" "40"\n'
       '"SizeMin" "10"\n"SizeMax" "20"\n"Alpha" "255"\n"StartDisabled" "1"\nsolid\n{\n'
       + ''.join('side\n{\n"plane" "%s"\n"material" "TOOLS/TOOLSTRIGGER"\n}\n' % p for p in PLANES) + '}\n}\n'
       'entity\n{\n"classname" "env_smokestack"\n"targetname" "chimney"\n"origin" "0 0 300"\n}\n')


class Ctx:
    def __init__(s): s.log = []; s.todo = []; s.files = {}
    def write(s, rel, data): s.files[rel] = data if isinstance(data, bytes) else data.encode()


class Smoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); self.vmf = os.path.join(self.tmp, 'm.vmf')
        with open(self.vmf, 'w') as fh: fh.write(VMF)
        m = V.Map(watervol.TEMPLATE); dmx.geta(m.E[m.world], b'children')[2] = []
        self.stack = m.new_entity('env_smokestack', [0, 0, 300], {'targetname': 'chimney', 'InitialState': '1', 'Rate': '10', 'Speed': '40',
                                                                   'JetLength': '200', 'rendercolor': '200 50 50', 'SmokeMaterial': 'particle/SmokeStack'}, angles=(0, 90, 0))
        self.trail = m.new_entity('env_spritetrail', [0, 0, 0], {'targetname': 't', 'parentname': 'ball', 'lifetime': '1', 'startwidth': '8'})
        r = m.new_entity('logic_relay', [0, 0, 0], {'targetname': 'r'})
        m.add_conn(r, 'OnTrigger', 'chimney', 'TurnOff'); m.add_conn(r, 'OnTrigger', 'motes', 'TurnOn'); m.add_conn(r, 'OnTrigger', 'chimney', 'Rate', '5')
        self.m = m; self.relay = r

    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_convert(self):
        c = Ctx(); m = self.m
        n = smokestack.run(m, c, self.vmf)
        self.assertEqual(n, 3)                                   # stack + trail in place, motes from the VMF (stack not added twice)
        ps = m.by_class('info_particle_system')
        self.assertEqual(len(ps), 3)
        eff = {m.name(e): (m.P(e, 'effect_name'), m.P(e, 'start_active'), m.origin(e), m.P(e, 'parentname')) for e in ps}
        self.assertTrue(eff['chimney'][0].startswith('particles/port_smoke/smokestack_')); self.assertEqual(eff['chimney'][1], '1')
        self.assertEqual(eff['motes'][1], '0'); self.assertEqual([round(x) for x in eff['motes'][2]], [64, 64, 32])
        self.assertEqual(eff['t'][3], 'ball')
        self.assertIsNone(m.P(self.stack, 'SmokeMaterial')); self.assertEqual(m.g(self.stack, b'angles'), [0.0, 0.0, 0.0])
        for rel, data in c.files.items():
            self.assertTrue(rel.startswith(('particles/port_smoke/', 'materials/port_smoke/')))
            if rel.endswith('.vpcf'): self.assertTrue(kv3text.loads(data.decode()).root['m_Initializers'])
        ins = sorted(m.conn_tuple(cc)[2] for cc in m.conns(self.relay))
        self.assertEqual(ins, ['Rate', 'Start', 'Stop'])
        self.assertTrue(any('Rate' in t for t in c.todo))
        self.assertEqual(smokestack.run(m, Ctx(), self.vmf), 0)   # rerun: nothing added again

    def test_names_carry_values(self):
        a, _ = smokestack.particle('env_smokestack', {'rate': '10'}); b, _ = smokestack.particle('env_smokestack', {'rate': '10'})
        c, _ = smokestack.particle('env_smokestack', {'rate': '11'})
        self.assertEqual(a, b); self.assertNotEqual(a, c)


if __name__ == '__main__':
    unittest.main()
